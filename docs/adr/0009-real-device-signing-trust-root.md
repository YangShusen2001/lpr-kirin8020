# ADR-0009 · 真机装机：信任根决定成败

- **状态**：已接受
- **日期**：2026-09-22
- **前置**：ADR-0008（探针控制台重设计）
- **证据**：`tools/sign_hap_huawei.sh`、`tools/deveco_pwd.py`、`tools/cert_root_cn.py`；
  设备 hilog `C011FE/foundation/HapVerify`

## 问题

重设计后的 HAP 构建通过、本地 `verify-app` 报成功，但装到用户真机上被拒：

```
failed to install bundle. code:9568257 error: fail to verify pkcs7 file.
    AppMod finish
```

这个报错的措辞极具误导性 —— 它看起来像**证书过期 / 签名算法 / 包名不匹配 /
UDID 不在白名单**。四条路都查过，全不是。

## 决策

**装机前先判定信任根；信任根不对，改什么都白费。**

### 根因

设备侧 hilog（`hdc shell hilog -x | grep -a HapVerify`）给出了唯一有效信息：

```
E C011FE/foundation/HapVerify: [hap_cert_verify_openssl_utils.cpp(GetCertsChain:322)]
    it do not come from trusted root,
    issuer: C=CN, O=OpenHarmony, OU=OpenHarmony Team, CN=OpenHarmony Application Root CA
E C011FE/foundation/HapVerify: [hap_verify_openssl_utils.cpp(VerifyCertChain:123)]
    get cert chain for signInfo failed
E C011FE/foundation/HapVerify: [hap_verify_v2.cpp(VerifyAppPkcs7:176)]
    GetCertChains from pkcs7 failed
E C01121/foundation/BMSInstaller: [bundle_install_checker.cpp:CheckMultipleHapsSignInfo:275]
    hap file verify failed
```

**用户真机是华为商用机（`MIA-AL00` / HarmonyOS 6.1.0.135 / API 24），
信任的是 `Huawei CBG Root CA G2`；而 `.signing/` 里的材料来自
OpenHarmony 官方 SDK（`sdk/.../toolchains/lib/OpenHarmony.p12`），
信任根是 `OpenHarmony Application Root CA`。两者是互不相认的两个信任域。**

于是本地 `verify-app` 只验摘要（通过），设备侧一验信任链就断。

### 修法

**换用 DevEco Studio「自动签名」为项目生成的华为材料重新签名。**

用户本机 `~/.ohos/config/` 里**已经存在**这套材料，是 9 月 17 日 DevEco
给本工程做自动签名时写的：

```
default_LprDemo_4-KxTwabmfaI1ewvk8KnhVET4lfBdGRShGJsTXnE3DA=.{p12,cer,p7b}
```

- 信任根：`Huawei CBG Root CA G2` ✓
- profile 的 `device-ids` **已包含真机 UDID** `7DD1D359…08B4`（`hdc shell bm get -u` 一致）
- bundle-name：`com.shusen.lprdemo`（与 `AppScope/app.json5` 一致）

关键链路：`tools/sign_hap_huawei.sh`。

## 三个复现要点

### 1. `.p12` 口令是 DevEco 加密串，要解出来

`build-profile.json5` 里的 `storePassword` / `keyPassword` 是被加密的
（AES-128-GCM 密文，84 字符 hex）。`tools/deveco_pwd.py` 负责解出明文。
（**不要在文档里贴密文片段** —— 本 ADR 初稿贴了前后几位做示例，
被 `tools/scan_for_publication.py` 判成设备序列号并阻断。）

**做法是直接 `require()` DevEco 自带的
`tools/hvigor/hvigor-ohos-plugin/src/utils/decipher-util.js`**，
用一个最小 stub 顶掉它依赖的 `@ohos/hvigor` 日志模块。

**不要自己重新实现这个算法。** 我试过，两次都错，且错法很隐蔽：

- `DecipherUtil.getRootKey` 里写的是 `pbkdf2Sync(s.toString(), salt, 1e4, 16, "sha256")`，
  `s` 是 `Int8Array`。**`Int8Array` 没有覆写 `toString()`**，于是退化成
  `Array.prototype.toString()`：每个元素按**十进制**转文本、用 `,` 连接，
  且元素是**有符号** int8。本机这份 32 字节的 x 会变成 120 个 ASCII 字符，
  形如 `"48,-102,-18,-77,...,-64,119"`（`0x30` → `"48"` 是数字 48，不是字符 `'0'`）。
  网上把它当 hex / latin1 的解读**都是错的**。
- salt 侧走的是 `Buffer.from(Int8Array).toString('latin1')` 的**膨胀**语义：
  Buffer 的 `'latin1'` 解码对 >0x7F 的字节走 utf8 lone-surrogate，产出 U+DC80..U+DCFF，
  编码回 bytes 时该字节占 **3 个字节**。

**两侧不是同一种编码。** 只要有一处还原不准，PBKDF2 出来的 rootKey 就是另一个值，
后续 GCM 直接 `InvalidTag` —— 而且**不会告诉你错在哪**。

> 结论：能用原版就用原版。附带好处是 DevEco 升级后算法若有变化，
> 脚本自动跟随，不会因版本漂移而悄悄解错。

### 2. 证书链的信任根要看 Issuer CN，别用 `grep 'CN='`

DN 在 DER 里是 `SEQUENCE of SET of SEQUENCE{OID, UTF8String}` ——
`CN` 的 ASCII 与 `=` 之间**隔着 OID 与长度字节**，不是明文相邻。
所以 `grep 'CN='` 在 DER 上必然抓空（这个坑踩过）。

正确做法：`keytool -printcert -rfc` 拿 PEM（纯 ASCII，避开 GBK 输出乱码），
再用 X.509 解析器读 Subject/Issuer。→ `tools/cert_root_cn.py`

实测两条链：

| 材料 | 信任根 CN |
|---|---|
| `.signing/lpr-app.cer`（OH 官方） | `OpenHarmony Application Root CA` |
| `~/.ohos/config/default_LprDemo_*.cer`（华为） | `Huawei CBG Root CA G2` |

### 3. UDP 白名单曾是误判方向

一度以为是 profile 的 `device-ids` 没包含真机 UDID。确实 `.signing/` 的
OH profile 里只有两台**云手机** UDID，但**改 UDID 也没用** ——
信任根不对，白名单再对也过不去。这个弯路记得记下来，省得下次再走。

## 后果

- **装机材料不再只有一套。** 按目标设备选：
  - `tools/sign_hap.sh` → OH 官方材料 → **云手机 / OH 开发板**（信任 OH 根）
  - `tools/sign_hap_huawei.sh` → 华为材料 → **华为商用真机**（信任华为根）
- **`tools/make_signing_material.sh` 增加 UDID 白名单注入**：
  自动从 `hdc shell bm get -u` 取目标真机 UDID 写进 debug profile
  （可用 `LPR_DEVICE_UDID` / `LPR_EXTRA_UDIDS` 覆盖）。
  这条对 OH 材料路径有意义（云手机的 profile 白名单要逐台补）。
- **新增诊断入口**：装机失败先跑
  `hdc shell hilog -x | grep -a HapVerify`，
  不要按报错字面（pkcs7 / 时长 / 包名 / UDID）逐条查。
- HAP 已成功安装并启动：`install bundle successfully` /
  `start ability successfully`，进程 `com.shusen.lprdemo` 存活。

## 边界声明

- 本 ADR **不**改动任何探针的测量逻辑，也不改 UI —— 只解决「怎么把包装到真机」。
- 华为材料是**用户账号专属的调试材料**，只在本机 `~/.ohos/config/`。
  任何脚本都**不内置**密钥；`deveco_pwd.py` 只是解密器，不含凭据。
- 调试 profile 有有效期（本机材料到 2051），但 `device-ids` 绑定设备 ——
  换机器要重新在 DevEco 里生成材料。

## 验证快照（2026-09-22）

| 项 | 结果 |
|---|---|
| `tools/deveco_pwd.py --verify` | 解出 `storePassword`，keytool 打开 `.p12` 通过 |
| `tools/cert_root_cn.py <华为 cer>` | `Huawei CBG Developer Relations CA G2`（rc=0） |
| `tools/sign_hap_huawei.sh` | `sign-app success` + `verify-app success` |
| `hdc install -r` | **`install bundle successfully`** |
| `hdc shell aa start` | **`start ability successfully`**，进程存活 |
| 真机截屏配色审计 | 暗像素 86.4%，强调色精确 `#4C9AFF`，无旧浅色系残留 |
