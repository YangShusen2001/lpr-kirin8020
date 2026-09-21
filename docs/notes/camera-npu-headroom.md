# 相机路的 NPU 余量：谁在吃帧预算

**日期**：2026-09-21
**触发**：用户问「NPU 好像基本能跑满了，刚改了 320×320？还能不能提高相机帧率？
我看延迟有 20~25 ms，那应该能到 40~50 帧？有时候延迟还能在 13 ms，是怎么回事？」
**结论**：**三个前提都要纠正**，然后问题才有解。

1. **320×320 不存在** —— 全 git 历史里 `ANALYZE_TARGET_W` 只有 640，真机预览档里也没有 320。
2. **「NPU 跑满了」不可测** —— 硬约束，本项目禁止任何利用率数字（ADR-0003）。
3. **20–25 ms → 40–50 帧是算术用错了量** —— `1000/p50` 是服务时间倒数，不是 fps；
   相机侧上限实测 **~30 fps**，40–50 帧在这条路上不可达。

而「20–25 ms」与「13 ms」的差别**不是抖动，是条件不同**：一个是生产档未检出，
一个是全 NPU 档未检出。分桶后一切都对上了。

**真正的答案**：生产档在有车牌时 **frame p50 = 40 ms > 33.3 ms 预算（余量 −6.7 ms）**，
所以到不了 30 fps。而**吃预算的是 CPU 上的检测段（19.6 ms），不是 NPU 上的识别段（4.0 ms）**。
「榨干 NPU」在这条流水线上已经不是瓶颈了 —— 继续压 NPU 收益极小。

---

## 一、被纠正的三个前提

### 1.1 「刚改了 320×320」——不存在

| 检查 | 结果 |
|---|---|
| `ANALYZE_TARGET_W` 全部 git 历史 | **只有 640**，从未出现 320 |
| 真机预览档列表（`PROFILES[0]`，24 档） | 480x480 / 640x480 / 720x720 … **没有 320 宽的档** |
| 真机 `STREAM START` | `show=960x960 analyze=640x480 rot=90` |
| native 回传 | `wh=480x640`（rot=90 后宽高互换） |

你记的 320 是**检测器自己的输入边长**：`MODEL_DET = models/y5fu_320x_head_fp32.ms`，
`inputShape=[1,320,320,3]`，native 侧 `LprSessions::detSize = 320`
（`lpr_pipeline.h:105` 声明、`napi_init.cpp:824` 默认构造，**没有参数能传**）。自 T1 起未变。

### 1.2 「NPU 基本跑满了」——不可测，且是硬约束

ADR-0003 与 `AGENTS.md` 硬约束 1：NPU 利用率**物理上不可读** —— 应用侧不行，`hdc` 侧也不行
（DevEco Profiler / SP_daemon / hiperf 对 NPU 都没有负载计数器；SP_daemon 只有 `npu_thermal`，
那是**温度**不是负载）。**本笔记不产出任何利用率数字。**

替代证据形态（本项目唯一允许的）：**延迟余量 + 逐算子落点 + 张量指纹**。

### 1.3 「20–25 ms → 40–50 帧」——算术用错了量

`1000 / p50(frameMs)` 是**服务时间的倒数**，不是 fps。`CONTEXT.md` 把
「服务时间 / 到达率 / 完成率」定义为三个量，**只有后两者可以对外称 fps**。

相机侧硬上限由两个独立档位同时锚定：

| 档位 | 说明 | 实测到达率 |
|---|---|---|
| 基准档（gear 3） | 只取帧，不推理 | **29.99 fps**（26.93–30.18，50 窗口，0 丢帧） |
| callback 档（gear 4） | 只数回调，连帧都不取 | **≈30.0 fps**（26 窗口） |

所以相机路的天花板就是 ~30 fps；40–50 帧不可达。
但 **20–25 ms 这个数本身有意义** —— 它是每帧成本，余量 = `33.3 − frameMs`。

---

## 二、核心：13 ms 与 20–25 ms 是两个不同条件

同一份归档日志（`evidence/t3_camera_30fps_release.log`）按 `count` 分桶：

| 档位 | 未检出（count=0） | 检出（count>0） |
|---|---|---|
| 生产档 infer p50 | **20.30 ms**（n=92） | **30.32 ms**（n=21，max 140） |
| 全 NPU infer p50 | **13.64 ms**（n=27） | 33.14 ms（n=1，样本不足） |

即：**13 ms ≈ 全 NPU + 未检出**，**20–25 ms ≈ 生产档 + 未检出**。

**为什么界面读不出来**：`record()` 把**所有帧**塞进同一个滑窗取 p50，
而检出帧要多跑矫正 + 识别 + CTC + 判色。混桶得到的是两种分布的混合物。
`STAGE` 行每 30 帧才打一条，正好是混合后的抽样。

**修法**：`infer`/`conv` 桶按 `count > 0` 拆开；`frameMs` 不分桶（吞吐关心每帧实际墙钟）。

---

## 三、复采结果：生产档余量为负，瓶颈在 CPU 检测段

**协议**（`tools/run_camera_sweep.ps1`，档位由 `uitest uiInput click` 外部驱动）：

| 项 | 值 |
|---|---|
| 稳态门 | 开流后 **45 s** 不计入统计（相机爬坡） |
| 每档观测 | 60–90 s |
| 分析路 | 640×480（rot=90） |
| 构建 | release（`-O2`，已过 `check_native_build_flags.py`） |
| 热档 | 4（电池 43 ℃）—— **跨轮比较只在同热档内做** |

### 3.1 逐档余量表

| 档位 | 到达 fps | 未检出 frame p50 | 检出 frame p50 | 检出余量 vs 33.3 ms |
|---|---|---|---|---|
| **生产**（det=CPU rec=NPU） | 24.79（20.62–28.63） | 30.0 ms | **40.0 ms** | **−6.7 ms（超预算）** |
| **全 NPU**（det/rec=NNRT） | **29.96**（26.30–30.42） | 21.5 ms | 28.0 ms | **+5.3 ms** |
| 基准（只取帧） | 29.99 | — | — | 相机上限 |

**读法**：生产档在**有车牌**时每帧要 40 ms，而相机只给 33.3 ms —— 我们比相机慢，
所以到达率被拖到 24.8 fps。全 NPU 档把检出帧压到 28 ms，才有 5.3 ms 余量贴住 30 fps。

### 3.2 谁在吃预算：CPU 检测段 19.6 ms vs NPU 识别段 4.0 ms

检出帧的完整账（`sweep1` gear=0，`STAGE` 的 `stages=` 字段 n=81；全部为 **native 侧**）：

| 段 | 落点 | p50 | 占 frame 40 ms 的比例 |
|---|---|---|---|
| JS prep（取帧 + 组件拷贝） | JS | 1.00 ms | 2.5% |
| **native conv**（NV21→RGBA **+ 1.2 MB rgbaSum 校验和**） | CPU | **7.15 ms** | 17.9% |
| **检测段（detect 合计）** | **CPU** | **19.61 ms** | **49.0%** |
| ├ letterbox | CPU | 2.49 ms | |
| ├ encode + infer（det 前向） | **CPU** | **15.59 ms** | |
| └ decode + NMS | CPU | 0.03 ms | |
| rectify（透视矫正） | CPU | 0.49 ms | 1.2% |
| **识别段（recog）** | **NPU** | **3.98 ms** | **10.0%** |
| cls（判色，像素测量） | CPU | 0.08 ms | 0.2% |
| NAPI + 调度 + 残差 | — | ~7.7 ms | 19.2% |
| **合计 frame** | | **40.00 ms** | 100% |

> ⚠️ **口径警告（我在这张表上先错过一次）**：`STAGE` 行的 `conv=` / `infer=` 是 **native 侧**的值；
> `RATE` 行的桶是 **JS 侧**的值（`prep` = JS 取帧拷贝，`rt` = JS↔native 整段往返）。
> 两者**不是同一个量**：`rt`(39.0) ≠ native `infer`(25.6)，差的就是 native conv + NAPI。
> 早先我把 native `conv` 当成「JS prep」写进表里（7.15 被标成 JS 侧），是错的 ——
> 真实 JS prep 只有 **1.00 ms**。字段已改名（见 §6.2），但读旧数据时仍要看清是哪一侧。

**这就是本轮最重要的结论**：**检测段（CPU）比识别段（NPU）贵 5 倍。**
「榨干 NPU」在这条流水线上**已经不是主要矛盾** —— 识别段只占 3.98 ms（10%），
即便把它压到 0，也救不回生产档那 −6.7 ms 的缺口。

### 3.2b 复采复现性（`sweep2`，热档 3）

| 段 | sweep1（热档 4） | sweep2（热档 3） |
|---|---|---|
| JS prep | 1.00 | 1.00 |
| native conv | 7.15 | 7.32 |
| 检测段 | 19.61 | 23.75 |
| 识别段（NPU） | 3.98 | 3.75 |
| frame（检出） | 40.00 | 36.00 |
| 到达 fps | 24.79 | 26.45 |

方向一致：**检测段是最大项，识别段恒定 ~4 ms**。绝对值的差主要来自热档
（sweep1 热档 4 / 43 ℃，sweep2 热档 3 / 41 ℃）—— 这正说明**跨热档不可直接比**。
识别段在热档 3→4 之间只动 0.23 ms，**进一步佐证它不在关键路径上**。

> ⚠️ **一处未解释的残差，记在这里而不是抹平**：
> 两轮的「native 分段之和」与「RATE frame」对不齐的程度**不同**：
>
> | | native 分段之和 | RATE frame | 残差（NAPI/调度等） |
> |---|---|---|---|
> | sweep1（热档 4） | 1.00+7.15+19.61+0.49+3.98+0.08 = 32.31 | 40.00 | **+7.69** |
> | sweep2（热档 3） | 1.00+7.32+23.75+0.61+3.75+0.13 = 36.56 | 36.00 | **−0.56** |
>
> sweep2 的分段几乎**完全解释了** frame，sweep1 却多出 7.7 ms。
> 可能原因（**未验证**）：`STAGE` 每 30 帧才抽样一条，两轮抽样条数不同
> （sweep1 n=81 / sweep2 n=45），且 `STAGE` 与 `RATE` 的**统计窗口不对齐** ——
> `STAGE` 是抽样点，`RATE` 是 2 s 滑窗，两者覆盖的时间段不重合时，
> 「分段之和 ≈ frame」这个恒等式就不成立。
> **这不影响主结论**（检测段 ≫ 识别段，两轮一致），
> 但说明**逐段绝对值目前不能当作精确分解**，只能当作量级判断。
> 要拿到精确分解，得让 `STAGE` 与 `RATE` 共用同一批样本（登记为后续改进）。

### 3.3 全 NPU 档为什么能到 30：它省的是检测段

全 NPU 档把检测段从 CPU 挪到 NPU，检出帧 40.0 → 28.0 ms。但**这一档读错参考图**
（`det-backend-alters-result.md`：`cropSum` 2773473 → 2763123，`D` 被读成 `0`）。
**所以它不是可用的提速手段，只能用于性能上限测量。**

---

## 四、查官方文档后的补充（本地 `HuaweiDocs` 语料 + 在线文档）

本地语料：`C:\Users\26671\Desktop\HuaweiDocs\cn`（8877 篇 `.md`，含
`harmonyos-guides` / `harmonyos-references` / `design-guides`，与线上文档同源同步）。
在线 `developer.huawei.com/consumer/cn/doc/HarmonyOS-Guides/camera-kit` 是 SPA，
正文经 POST `documentPortal/getDocumentById` 注入，`web_fetch` 只拿到「文档中心」——
**因此以本地语料为准**（同一份内容，可全文检索）。

### 4.1 `setFrameRate` 有**重复调用**约束（直接影响我们的切档）

`camera-framerate.md:98-99` 与 `camera-setframerate-native.md:116-117` 明确：

> * 设置**非固定**帧率后，**不支持再次调用**该接口重新设置动态帧率。
> * 设置**固定**帧率后，支持重新设置固定帧率，但**必须保证新设置的帧率可以整除
>   之前设置的帧率或者被之前设置的帧率整除**。

我们设的是 `30-30`（min==max，属**固定帧率**），所以重复设置受整除约束。
这解释了 `camera-60fps-research.md` 里「60 被接受但拿不到 60」之外的一个**新风险**：
`30 → 60` 可整除（60/30=2，合法），但 **`60 → 30` 之后再想回 `60` 是否仍合法、
以及跨 gear 反复 `setFrameRate` 会不会静默失效**，我们**从未验证**。
本轮的切档协议每档都重新开流（`STREAM START`），所以每次都从干净会话开始，
这条约束暂时不影响本轮数据 —— **但若将来做「不重开会话的动态调档」，必须先验这条。**

### 4.2 `HIGH_FRAME_RATE` 场景模式**未对三方开放**（SDK 级确证）

`camera-60fps-research.md` 第 1c 题记「C++ 内部有 `SceneMode::HIGH_FRAME_RATE = 13`，
但未暴露给应用」。本轮**直接在本地 SDK 里复核**：

```
D:\IDE\DevEco_Studio\sdk\default\openharmony\ets\api\@ohos.multimedia.camera.d.ts
  L2493  enum SceneMode {
  L2508      NORMAL_PHOTO = 1,
  L2527      NORMAL_VIDEO = 2,
  L2548      SECURE_PHOTO = 12
         }
grep HIGH_FRAME|HIGH_SPEED|SLOW_MOTION|高帧  →  0 命中
```

**ArkTS 侧只有 3 个成员，没有任何高帧率/慢动作模式。** 结论与既有笔记一致，
但这次是**对 SDK 文件的直接复核**，不是转述。→ 60 fps 在应用层**无路可走**。

### 4.3 `SystemPressureLevel`：**API 20+，我们可用**（新发现的杠杆）

`camera-system-pressure.md`（ArkTS）与 `native-camera-system-pressure.md`（C/C++）：

> 从 API version 20 开始，相机框架提供对**系统压力等级**的监听。
> 在长时间使用相机的场景（如直播业务）中，相机应用可以通过监听系统压力等级变化，
> **动态调整画质（如帧率、分辨率等）**，平衡功耗、发热和系统负载，保证功能长时间可用。

```ts
enum SystemPressureLevel {          // @since 20，本地 SDK L6421 确认存在
  SYSTEM_PRESSURE_NORMAL   = 0,     // 正常
  SYSTEM_PRESSURE_MILD     = 1,     // 升高，但系统不主动管控
  SYSTEM_PRESSURE_SEVERE   = 2,     // 可能对图像质量、性能产生影响
  SYSTEM_PRESSURE_CRITICAL = 3,     // 对图像质量、性能产生显著影响
  SYSTEM_PRESSURE_SHUTDOWN = 4      // 过高，停止工作
}
// PhotoSession.on('systemPressureLevelChange', cb)
```

**为什么这条对我们重要**：我们在 `camera-fps-ceiling.md` 里观察到
相机 daemon 会在温度升高时把 `mCurMaxFps` 往下钳（`levelTempThreshold` 一类逻辑），
而**当时只能事后从 hilog 里猜**。这个 API 让我们能**在应用内实时拿到同一个信号**，
从而把「热致掉帧」从「不明抖动」变成「可标注的条件」。

**本轮未实现**（用户选的是「只做测量与定位」），登记为后续候选 **C6**：
把 `systemPressureLevelChange` 记进 `CAMRUN` 落盘行，与 `thermal=` / `battC=` 并列，
使「同一热档内比较」这条纪律有第二个独立维度。

### 4.4 官方文档明确要求「释放 Buffer」（印证 §6.1 的修复）

`camera-dual-channel-preview.md:26`（约束与限制）与 `camera-preview.md:1103`：

> 对 `ImageReceiver` 组件获取到的图像数据处理后，**需要将对应的图像 Buffer 释放**，
> 以确保 Surface 的 **BufferQueue 正常轮转**，防止出现**缓冲区溢出**等问题。
> 如果对 Buffer 进行异步操作，则需要在异步操作结束后，确保当前 Buffer
> 没有使用的情况下再释放该资源。

这正是 callback 档（§6.1）**从未跑通**的原因：原实现「不 `readLatestImage`、不 `release`」
直接违反了这条官方约束。**文档早就写了，我们是自己踩的。**

### 4.5 MindSpore Lite 侧：两个**未使用**的旋钮

查 `openharmony/native/sysroot/usr/include/mindspore/context.h` 与 `types.h`，
我们 `ms_engine.cpp` 当前只用了 `SetThreadNum` / `SetPerformanceMode(HIGH)` / `SetEnableFP16`，
另有三个**从未调用**的接口：

| 接口 | 取值 | 我们的现状 |
|---|---|---|
| `OH_AI_DeviceInfoSetPerformanceMode` | `..._HIGH=3` / **`..._EXTREME=4`** | 只设到 `HIGH`，**`EXTREME` 未试** |
| `OH_AI_ContextSetThreadAffinityMode` | 0 无绑定 / 1 大核优先 / 2 小核优先 | **未设**（默认无绑定） |
| `OH_AI_DeviceInfoSetPriority` | NONE/LOW/MEDIUM/HIGH | **未设** |

`EXTREME`（"Ultimate performance mode"）是最直接的一个未试档。
但注意 **§3.2 的结论**：识别段只占 3.98 ms，即便 `EXTREME` 再快 20% 也只省 0.8 ms ——
**收益远小于检测段**。登记为 C7，优先级低于 C1–C4。

> **另一个被排除的线索**：`CANN Kit` 提供了 `HMS_HiAIOptions_SetTuningMode`
> （`HIAI_TUNING_MODE_AUTO/HETER`，在线调优）与 `SetTuningCacheDir`。
> 但它是 **CANN Kit 的 `OH_NNCompilation`** 接口，而本工程走的是
> **MindSpore Lite NDK**（`libmindspore_lite_ndk.so`，CMakeLists L14），
> 且 `SetTuningMode` 在 MS Lite 的 `context.h` 里**不存在**。
> → **不适用于本栈**，除非迁移到 CANN Kit。此处记录以免下次重复检索。

---

## 五、回答「还能不能提高相机帧率」

分两问，答案不同：

### 5.1 相机侧：不能。~30 fps 是硬上限

- 基准档 29.99 fps、callback 档 ≈30.0 fps —— 两个独立档位互证。
- 请求 60 fps 不被兑现（`camera-60fps-research.md` 已给源码级根因：
  框架零校验零复查，钳位在厂商闭源 daemon 的 `setMaxFps()`）。
- 降分辨率换不到帧率（`camera-fps-ceiling.md` 已证伪）。

### 5.2 流水线侧：生产档**到不了** 30，但缺口不在 NPU

生产档检出帧 40 ms，要贴住 30 fps 需要 ≤33.3 ms —— **缺 ~6.7 ms**。
按 3.2 的拆解，可动的候选按收益排序（**本轮只登记，不实现**）：

| # | 候选 | 预期收益 | 代价 / 风险 | 为什么可能值得 |
|---|---|---|---|---|
| C1 | 分析路 640×480 → 480×480 | conv 与 letterbox 按面积降，约 −2~3 ms（面积比 0.75） | 小车牌检出率下降 | 能省时间；**但不抬高相机上限** —— 见下 |
| C2 | **native conv**（NV21→RGBA，7.15 ms）改用 `libyuv` 或 NEON 手写 | 7.15 ms 里的一部分 | 需保证逐位一致（`cropSum` 不变） | **第二大项**，纯 CPU 优化 |
| C3 | ~~去掉/降频 rgbaSum 校验和~~ **（已撤销，见下）** | **≈0.16 ms，不值得动** | — | — |
| C4 | 检测段 CPU 多线程 / 绑大核（`SetThreadNum` 现恒 4；`SetThreadAffinityMode` **从未调用**） | 未知，可能 −2~4 ms | 需扫档；热态影响未测 | Index.ets 已有 `cpu_t{N}` 扫描档 |
| C5 | **det 换 NPU** | −12 ms | **读错参考图**（确定性） | ❌ 不可用，除非先解决数值敏感性 |
| C6 | 监听 `systemPressureLevelChange`（API 20+，见 §4.3）并落盘 | **0 ms（不省时间）** | 无 | **把热致掉帧从「不明抖动」变成可标注条件** —— 测量类，不是优化类 |
| C7 | NNRT `PERFORMANCE_EXTREME`（现为 `HIGH`，见 §4.5） | 预期 <1 ms | 需重编会话（受硬约束 2 限制） | 识别段本就只占 3.98 ms，收益上限很低 |

> **C1 的既有实测**：`CameraPage.ets:132-137` 记录过一次 480×480 + 请求 60 fps 的试验 ——
> `FPS SET active=60-60` 但实测 ~27 fps，与 640×480 下的 28–30 fps **没有差别**。
> 那次试验的**目的是换帧率**（失败：~30 是传感器/ISP 上限，与分辨率无关），
> 但它**没有测「480×480 是否省了 conv 时间」**（当时没有分桶计时，读数被混桶污染）。
> 所以 C1 在**降延迟**这个目标上**仍未验证** —— 它值得重测，但要配分桶计时。
> 代价是检出率：T3 选 640 正是为了小车牌，这条要一起称。
>
> **C2 的修正说明**：本节初稿把「JS 侧 NV21 拷贝」列为候选并估 7.15 ms，
> 那是把 **native `conv`** 误当成了 JS 侧开销（见 §3.2 的口径警告）。
> 真实 JS prep 只有 **1.00 ms** —— 即便全免也省不到 1 ms，故**撤销该候选**，
> 把预算移到真正的第二大项 native conv（C2）。
>
> **C3 的修正说明**：初稿估「去掉校验和能省 1~3 ms」，也是错的。
> 校验和已经优化过：`napi_init.cpp:862-878` 记录了主机微基准
> **0.6903 ms → 0.1642 ms（快 4.2x，逐位相等）**，且注释明确禁止改成抽稀采样
> （会漏检单字节改动，毁掉它作为等价性证据的价值）。
> 即**它现在只值 0.16 ms**，而 native conv 总计 7.15 ms —— 说明 conv 的 7 ms
> **几乎全是 NV21→RGBA 的逐像素整数运算本身**（`lpr_pipeline.cpp:1234-1259`，
> 30 万像素 × 每像素 3 次乘法 + 3 次 clamp + 旋转坐标计算），
> 不是校验和。**要省 conv 只能动那段像素循环（C2），不是动校验和。**

**C1–C4、C7 都不碰「识别段」**。这正是本轮方法学的落点：**「榨干 NPU」问错了对象** ——
在这条流水线上，NPU 那一段（3.98 ms）已经便宜到不值得再压。

---

## 六、附带修掉的两个仪器缺陷（都不改产品行为）

### 6.1 callback 档（gear 4）**从未成功运行过**

原实现「不 `readLatestImage`，不 `release`，只数回调」—— 听起来合理，实际是错的：
接收器只有 8 格，30 fps 下 ~0.27 s 填满，相机随即**停止回调** `imageArrival`。
于是这一档测到的不是「相机能回调多快」，而是「缓冲填满用了几帧」。

**证据**：全部归档日志里**没有任何 `gear=4` 行**；本轮首次运行时
12 s + 45 s + 90 s 全程 **0 个 RATE 窗口**，同时 `all buffer are using` 持续刷屏。

**修法**：照常 `readLatestImage` + `release`（只为腾空缓冲），不推理、不计延迟统计。
到达计数在抽帧**之前**已经记过，所以「数回调」的目的不受影响。
修复后实测：26 个窗口，`arrive≈30.0 / done=0`（正确签名：只数到达，不完成）。

### 6.2 字段名歧义：`infer_*` 实际是「往返」，不是 native `infer`

`record()` 拿到的是 `cameraFrameAsync` 的**整段往返**（NAPI + native conv + 流水线），
而 `STAGE` 行的 `infer=` 是 **native 侧**的纯流水线耗时。两者**不是同一个量**，
但早先都叫 `infer` —— 同一批数据里 `infer_hit_p50=39` 与 `STAGE infer p50=25.58` 并存，
看着像自相矛盾。

**修法**：桶字段改名 `rt_*`（round-trip）与 `prep_*`（JS 侧），
与 `STAGE` 的 native `conv=`/`infer=` 明确区分。**名字必须自带口径。**

---

## 七、采集纪律（写给下一轮）

1. **稳态门必须过**。开流后 ~30 s 到达率崩到 1.4–5 fps 再爬回 30
   （相机 daemon `setMaxFps mCurMaxFps=0 -> 27`，切档后才 `27 -> 30`）。
   `WARMUP_FRAMES = 10`（≈0.33 s）**完全不够**；现用 `SETTLE_MS = 45000`。
   未过门的读数会把 1.4 fps 的窗口算进「稳态」。
2. **必须分桶**。检出 / 未检出的 `infer` 差一倍以上，混桶 = 报混合分布。
3. **hilog 会滚掉**。16 MB 环形缓冲，实测一轮跑完约 40 分钟后 `LprCamera` 的行完全消失
   （本轮靠设备持久化文件 `/data/log/hilog/hilog.NNN.*.gz` 才恢复出 06:04 那轮）。
   **主证据必须是 App 自己落盘的 `filesDir/camera_run_<ts>.log`**，hilog 只作辅证。
4. **量性能前先跑 `tools/check_native_build_flags.py`**（不需要设备）。`-O0` 慢 4 倍且无报错。
5. **热档必须记录**。热档 2→3 时 NPU 延迟 +15~20%，跨轮比较只在同热档内做。
6. **观测不到时，先问「观测代码有没有被执行」**。5.1 的 callback 档就是
   「看着像回调停摆，实际是缓冲填满」；本轮还额外踩到「相机页没起来是因为权限弹窗」
   —— 两者症状都是「没有 STREAM START」，必须靠 dumpLayout 区分。

---

## 八、复现

```powershell
# 1) 构建（必须带 buildMode=release）
cd C:\Users\26671\lpr-kirin8020-app\LprDemo
$env:JAVA_HOME='D:\IDE\DevEco_Studio\jbr'
$env:PATH='D:\IDE\DevEco_Studio\jbr\bin;' + $env:PATH
$env:DEVECO_SDK_HOME='D:\IDE\DevEco_Studio\sdk'
Remove-Item Env:\NODE_OPTIONS -ErrorAction SilentlyContinue
& 'D:\IDE\DevEco_Studio\tools\hvigor\bin\hvigorw.bat' --mode module `
    -p product=default -p buildMode=release assembleHap --no-daemon

# 2) 装（先卸旧 App，同 bundleName 会混证据）
hdc uninstall com.shusen.lprdemo
hdc install -r entry\build\default\outputs\default\entry-default-signed.hap

# 3) 跑协议（档位由 uitest 外部驱动；自动处理权限弹窗）
cd C:\Users\26671\lpr-kirin8020-app
powershell -NoProfile -ExecutionPolicy Bypass -File tools\run_camera_sweep.ps1 `
    -Tag sweep1 -Gears 0,1,3,4 -ObserveSec 90

# 4) 解析（产出逐窗口 CSV + 逐档汇总，含余量表）
python tools\parse_camera_run.py evidence\camera_sweep1.log
```

证据：`evidence/camera_sweep1.log`（App 落盘，主）、`evidence/camera_sweep1.hilog.txt`（辅）、
`evidence/camera_windows.csv`、`evidence/camera_summary.md`。

---

## 九、与既有笔记的关系

- **不推翻**任何既有结论，但给三条补了口径：
  - `camera-fps-ceiling.md` 的「理论上限 35.0 / 42.7 fps」→ 那是服务时间倒数，不是 fps。
  - 同文「全 NPU 档 30.00 fps」→ 那批数据**全程未检出**且含相机爬坡期，只能作相机上限旁证。
  - `camera-fps-investigation.md` §一 的 `infer 24–32 ms` → 混桶读数，已分桶。
- **强化**了 `det-backend-alters-result.md`：det 换 NPU 的收益是 −12 ms，
  但代价是确定性读错 —— 现在有了它在帧预算里的确切占比。
- **方法学落点**：本轮的答案不是「NPU 还能榨多少」，而是
  **「先量清谁在吃预算，再决定榨谁」**。榨错了对象，收益上限是 3.98 ms。
