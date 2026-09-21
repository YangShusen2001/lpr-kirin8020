# 在麒麟 8020 上跑 NPU 推理：构建与环境类坑

> **这是什么**：一份「你会踩的坑」清单，不是教程。
> 每条按 **现象 → 根因 → 正确做法 → 可复现的最小验证** 四段写，
> 每条都给一条**你现在就能跑**的命令，跑完能亲眼看到结论。
>
> **适用面**：华为麒麟 8020（本工程实测机型 nova 14 Pro / MIA-AL00，
> HarmonyOS 6.1.0.135 / API 24）+ MindSpore Lite Kit → NNRT → NPU。
> 其中「非 ASCII 路径」「构建模式」两类坑**不限于麒麟**，
> 任何 HarmonyOS native 工程都会遇到。
>
> **配套**：运行时与落点类坑见 `NPU 指南（二）· 运行时与落点`（#17）。
> 本文件的每个数字都能在 `docs/evidence-index.md` 里找到对应行。

---

## 坑 1 · `-O3` 被静默废掉：native 代码实际以 `-O0` 跑

### 现象

相机页帧率约 **7 fps**，而「只取帧不做推理」的基准档能到 **20 fps**。
生产档 `arrive == done`、`dropped = 0` —— 相机没被我们拖住，但一经推理就掉到 7。

**看起来像「算法太慢」或「设备弱」。** 两处都很容易让人走错方向：
去优化算法循环、去怀疑 NPU 带宽、去砍模型。都不对。

### 根因

`entry/build-profile.json5` 里确实写了优化：

```json5
"externalNativeOptions": {
  "cppFlags": "-O3",        // 看起来已经开了
}
```

但 **hvigor 默认按 debug 构建**，于是 CMake 用 `CMAKE_BUILD_TYPE=Debug`，
并把它自己的 `-O0 -g` **追加在 `-O3` 之后**。
**编译器取最后一个 `-O` 参数**，`-O3` 被废掉。`build.ninja` 里的真实 FLAGS：

```
-fdata-sections ... -O3 -D__MUSL__ -O0 -g -fPIC
                   ^^^            ^^^
                   被废掉          实际生效
```

**没有任何报错、警告或日志。** 唯一的后果是全部 native 代码未优化运行。

**本机 `build.ninja` 里的原始编译行**（可直接核对，非转述）：

```
... addrsig -Wa,--noexecstack -Wformat -Werror=format-security  -O3 -D__MUSL__ -O0 -g -fno-limit-debug-info  -fPIC ...
                                                                 ^^^            ^^^
                                                                 被废掉          实际生效
```

### 正确做法

**构建时必须显式指定 release**（本工程已把它做成默认值，见 `build.sh`）：

```bash
BUILD_MODE=release bash build.sh assembleHap --mode module -p product=default
```

⚠️ **产物路径相同**（`entry/build/default/outputs/default/entry-default-signed.hap`），
debug/release 会互相覆盖 —— **装完要确认用的是哪一个**。

### 可复现的最小验证

**不需要设备**，读构建产物即可：

```bash
python tools/check_native_build_flags.py
```

它读 hvigor 生成的 `build.ninja`，取**最后一个** `-O` 参数并断言它不是 `-O0`。
本机实测输出：

```
[OK  ] release  生效 -O2      NDEBUG=有   LprDemo\entry\.cxx\...\release\arm64-v8a\build.ninja
通过：native 以优化模式构建，性能数据可用。
```

想看失败长什么样，就切到 debug 再跑一次：

```bash
BUILD_MODE=debug bash build.sh assembleHap --mode module -p product=default
python tools/check_native_build_flags.py
#   [FAIL] debug  生效 -O0   NDEBUG=无   ...
```

**真机侧的量级差**（同一台 nova 14 Pro、同一场景、只改构建模式）：

| 指标 | `-O0`（默认 debug） | `-O2`（`buildMode=release`） |
|---|---|---|
| 相机帧率（生产档） | **7 fps** | **20 fps** |
| `conv`（NV21→RGBA + rot90） | ~25 ms | **1.42 ms** |
| native 单帧合计 | ~86 ms | ~20 ms |

> **交叉佐证**：主机端 `-O2` 微基准（`bench_conv.cpp`，同样的像素数学与循环结构）
> 测出 `conv` = **1.412 ms**，与真机 `-O2` 的 1.42 ms 同量级。两个独立平台一致。

> **这条坑的另一个教训**：修好之后我曾怀疑 `rot=90` 的散射写是元凶，
> 微基准直接**证伪**了它 —— 散射代价仅 **4%**，而按 16×16 分块改写反而**慢 28%**。
> **这次测量的价值在于阻止了一次无用的重写。** 先量，再改。

**引用任何 native 延迟 / 帧率数字之前，先跑这个守卫。**

---

## 坑 2 · 路径里有中文：两个工具、两种报错、都是静默失败

### 现象

工程放在 `.../车牌识别/...` 这类含中文的目录下时，两件事会坏，
而且**看起来毫无关系**：

**(a) hvigor 构建失败**，报 `00306003`，但错误信息不指向路径。

**(b) CANN DDK 的 OMG 转换被拒**，报一个很像「参数写错」的错误：

```
failed validation of new value ... for flag 'output'
CheckOutputPathValid ... false
```

### 根因

两者是**同一类缺陷**：工具链对「输出/工程路径」做校验时，
**只接受纯 ASCII**，且**失败信息把原因归到参数上而不是路径上**。
看到 `for flag 'output'` 会以为是自己 `--output=` 传错了，实际是这个路径本身非法。

OMG 那条更隐蔽：它**先接受了参数、跑到校验阶段才拒**，
所以调用方拿到的是一句「参数值校验失败」，而不是「路径含非 ASCII」。

### 正确做法

**输出路径必须是纯 ASCII。** 两个具体做法：

1. **工程目录用纯 ASCII 路径**（本工程的做法：`~/lpr-kirin8020-app`，
   文档仓库才放在 `~/Desktop/车牌识别`）。文档仓库里不跑构建。
2. **OMG 的输出落到纯 ASCII 临时目录**，转完再拷回来：

```bash
# 错：--output=.../车牌识别/_scratch/om_rec
# 对：
bash ddk/tools/tools_omg/omg --model rec.onnx --framework 5 \
     --output /tmp/lpr_om/om_rec --platform kirin9020 \
     --input_shape input:1,3,48,160
```

> ⚠️ OMG 另有三条**同样是静默失败**的坑，一并记在这里（都实测踩到）：
> - **入口必须是包装脚本** `tools_omg/omg`，不是 `tools_omg/master/omg`。
>   包装脚本自己设 `LD_LIBRARY_PATH` / `CCE_LIB_DIR` / loader 软链；
>   直接跑二进制会报 `libomg.so not found` 或 unknown flag。
> - **不要传 `--target=omc`**：那会产 `.omc` 而非 `.om`，**而且 `rc=0` 静默成功**
>   （实测产出了 3 个 `.omc` 却一个 `.om` 都没有）。
> - **版本参数是 `--hiai_version`，不是 `--omg_version`**：
>   传后者会 `unknown command line flag` 然后**静默不出模型**。

### 可复现的最小验证

**一条命令，不需要设备也不需要 DDK**，直接观察「非 ASCII 路径」在
OMG 侧的行为与在 hvigor 侧的行为同源。先看本工程的路径自检：

```bash
python tools/paths.py
```

```
OK  LPR_DOC_REPO       <本机文档库路径>          ← 是中文，故意留着
OK  LPR_SCRATCH        <本机临时数据路径>        ← 纯 ASCII，故意这样
```

（上面两行是真实输出的原文，只把绝对路径换成了占位符 —— 名字本身不重要，
重要的是**一个含中文、一个纯 ASCII** 这个对比。）

注意 `LPR_SCRATCH`（临时数据/构建输出）**故意是纯 ASCII**，
而 `LPR_DOC_REPO`（只放文档）可以是中文 —— 这个分工就是为了绕开本坑。

检验「非 ASCII 输出路径会被拒」，最小可跑的是**直接构造一个含中文的输出路径**
喂给包装脚本，看 `CheckOutputPathValid` 是否为 false：

```bash
# 期望：被拒 + CheckOutputPathValid ... false
bash ddk/tools/tools_omg/omg --model cls.onnx --framework 5 \
     --output "$HOME/中文目录/om_cls" --platform kirin9020 \
     --input_shape input:1,3,48,160; echo "rc=$?"
```

> **`.om` 产物是否正确的判据**：magic 必须是 `IMOD`（`49 4d 4f 44`），
> 且**字节数与既有产物一致**。本工程三个生产模型（2026-09-20 实测复现）：
> `cls 841728` / `dethead 1010950` / `rec 5041253`。
> **SHA256 会不同** —— `.om` 内嵌时间戳与路径元数据，**尺寸一致才是可比证据**。

---

## 坑 3 · 固定 `batch = 1`：动态 batch 在构图阶段直接失败

### 现象

模型 ONNX 里的输入是动态 batch（`-1` 或 `N`），转换/加载时**直接抛错**，
且错误发生在 `OH_AI_ModelBuildFromFile` 阶段 —— 也就是**模型还没跑起来就失败了**。

### 根因

NNRT 通路对动态维度支持不全。带动态 batch 维度时，
`OH_AI_ModelBuildFromFile` 在**建图/形状推断**阶段就拒绝，
不会退化成「运行时慢一点」这种温柔形态。

> 同为动态维度，**动态 H/W** 与**动态 batch** 的处理也不一样 ——
> 本工程的做法是**全部固定**：`input_shape input:1,3,48,160`（识别器）
> 与 `1,3,H,W`（检测器），H/W 也按实际用到的固定尺寸转。

### 正确做法

**转换时就固定 batch = 1，不要指望运行时自适应。**

```bash
converter_lite --modelFile=rec.onnx --fmk=ONNX \
               --inputShape=input:1,3,48,160 \
               --outputFile=rec
```

推理侧**永远按 1 张图喂**，多图就循环调用。

### 可复现的最小验证

`.ms` 转换链**不需要华为账号**，`converter_lite.exe` 2.6.0 在
`<MSLITE_DIR>/mindspore-lite-2.6.0-win-x64/tools/converter/converter/`。
最小验证 = **转两份、比结果**：

```bash
# (a) 固定 batch=1 —— 期望成功
converter_lite --modelFile=cls.onnx --fmk=ONNX \
               --inputShape=input:1,3,48,160 --outputFile=cls_fixed

# (b) 动态 batch —— 期望在构图阶段失败
converter_lite --modelFile=cls.onnx --fmk=ONNX \
               --inputShape=input:-1,3,48,160 --outputFile=cls_dyn
echo "rc=$?"
```

**判据**：`(a)` 产出 `.ms` 且 `rc=0`；`(b)` 报错、不产出可用模型。
本工程三个生产模型在 `(a)` 下**已实测转换成功，且 SHA256 与项目自带 `.ms` 一致**。

> **为什么强调「转换时就固定」**：动态 batch 不是「转出来但慢」，
> 而是**根本转不出/载不进**。这一点与「动态形状只是性能差一点」的直觉相反。

---

## 坑 4 · 模型会话必须常驻：析构会 cppcrash

### 现象

模型会话（`OH_AI_Model*` + NNRT delegate）在**析构路径上崩溃**，
表现为 native 层 cppcrash。触发场景很典型：

- 进页面建会话、退页面销毁 → 反复几次后崩
- 想「跑完一次清一下省内存」→ 反复建/销毁后崩
- 长跑探针里周期性重建会话保「干净」→ 崩

**它不会每次都崩**，所以很容易被误判成「偶发」「设备问题」。

### 根因

**NNRT delegate 的析构路径本身有缺陷**。这不是用量问题、也不是并发问题 ——
是「销毁这个对象」这个动作在特定条件下会崩。
本工程的记录在 `docs/spec.md`：

> **会话常驻**：NNRT delegate 析构路径存在 cppcrash，
> 模型会话在应用生命周期内复用、不重建。

这条**直接约束了实验设计**：RQ4 热特性要求 App 能跑**长时间循环（≥20 分钟）**，
如果会话管理做成「每次进页面重建」，长跑实验根本做不成
（见 `docs/adr/0007-scope-rq3-rq4-only.md`）。

### 正确做法

**模型会话在应用生命周期内复用，不重建。**

- 会话在**首次用到时创建一次**，之后全局复用；
- **不在页面 onDisappear / 退后台时销毁**；
- 想省内存就**别建第二个**，而不是「建了再销毁」；
- 若确实需要多档模型切换（本工程有 CPU/NPU 对照需求），
  也要**保持各档会话常驻**，而不是切换时重建。

> **与「固定 batch=1」是配套的**：既然会话常驻、batch 固定，
> 那么「换输入」只能靠**改写输入张量**，不能靠重建会话。
> 本工程的落点对照探针（同一会话跑 CPU/NPU 两档）就是这么做的。

### 可复现的最小验证

**真机 + 一条循环**，观察是否崩在析构：

```bash
# 建/销毁会话 N 次，看是否 cppcrash
hdc shell aa start -a EntryAbility -b com.shusen.lprdemo
# 触发「反复建/销毁」探针（本工程 Index.ets 里有对应入口）
hdc shell hilog -x | grep -iE "cppcrash|CPP_CRASH|SIGSEGV|libnnrt"
```

**判据**：反复建/销毁的路径下 `cppcrash` 出现；
改成**复用同一会话**后不再出现。

> ⚠️ **这条坑的验证成本高于前三条**（要真机、要触发特定时序），
> 所以更实际的做法是**把它当设计约束接受下来**：
> 会话常驻本来就是合理的工程选择，不差这一个理由。
> 真正要防的是**「为了干净而重建」**这种看似正确的直觉。

---

## 四条坑的横向对照

| # | 坑 | 失败形态 | 最坑的地方 | 验证成本 |
|---|---|---|---|---|
| 1 | `-O3` 被 `-O0` 覆盖 | **静默**，无报错无警告 | 症状像「算法慢」，会引向无用的优化 | 低（无需设备） |
| 2 | 非 ASCII 路径 | 报错**指向参数不指向路径** | 以为参数传错了，反复改参数 | 低 |
| 3 | 动态 batch | **构图阶段直接失败** | 与「动态形状只是慢一点」的直觉相反 | 低（无需设备） |
| 4 | 会话析构 cppcrash | **间歇**，不是每次 | 像「偶发/设备问题」，难以稳定复现 | **高（真机+时序）** |

**共同主题：这四条里有三条是「静默失败」或「错因报错」。**
在嵌入式工具链上工作，**「没有报错」不等于「配置正确」** ——
所以每条都必须配一个**独立于构建过程的验证手段**
（`#1` 读 `build.ninja`、`#2` 看产物 magic/字节数、`#3` 对比两份转换结果）。

---

## 引用本文件时的注意事项

- 本文所有性能数字来自 **nova 14 Pro / 麒麟 8020 / API 24 / release `-O2`**。
  换机型、换构建模式**不可直接引用**。
- `7 fps → 20 fps`、`conv 25 → 1.42 ms` 是**同一台机器同一场景、只改构建模式**的对照。
  其中 `25 ms` 是 `-O0` 的产物，**不是这段代码的真实成本** ——
  真实成本是 `1.42 ms`（主机独立微基准 1.412 ms 佐证）。
- 本文**不主张** OMG（CANN）比 MindSpore Lite 更好或更差。
  OMG 相关的坑只说明**转换链能否跑通**，不涉及性能排序。
- 数字与 `docs/evidence-index.md` 的一致性由
  `tools/verify_published_numbers.py` 守卫（当前 **67 项全通过**）。
