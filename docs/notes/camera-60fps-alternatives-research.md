# >30 fps 相机帧的替代路径：hilog 反常数据解释 + 文档/API 面穷举

**日期**：2026-09-23
**设备**：HUAWEI nova 14 Pro（MIA-AL00）· 麒麟 8020 · HarmonyOS 6.1.0.135 · API 24
**SDK**：`<SDK>\default\`（apiVersion 24 / HarmonyOS 6.1.1）
**语料**：`<DOCS_CORPUS>\cn`（8877 篇，与 developer.huawei.com 同源）
**前序**：`camera-60fps-research.md`（2026-09-22，本轮不推翻其任何结论，只补增量与一处口径澄清）

**一句话结论**：`hilog_recovered.txt` 里的 `fps=43~58` 是**单帧处理耗时的倒数（流水线吞吐能力）**，
不是相机到达率 —— 同一段日志里真正的到达率（`RATE arrive=` 行）是 29.7~30.8 fps，
所以**「恒为 ~30」没有被推翻**；文档面与 API 面穷举后，仍**不存在**任何官方写给三方的
>30 fps 相机预览/分析流路径，唯一值得真机一试的增量路径是
**VideoSession（NORMAL_VIDEO）+ videoProfile 60fps + 双流帧率耦合规则**（camera-recording.md L74-78）。

> **【2026-09-21 真机复测更新】** 上面说的"唯一可行动增量"已经真机跑通，且**结果超出预期**：
> 双流耦合路径真的兑现了 60fps —— 预览/分析流到达率实测 **39~58.35 fps（0 丢帧）**，
> **推翻了「30 fps 是相机侧硬上限」的既有结论**。详见文末**第四节**。

---

## 一、结论表

| # | 问题 | 结论 | 证据强度 |
|---|---|---|---|
| 1 | `FRAME n=… fps=43~58` 是什么 | `1000 / p50(单帧处理耗时)`，窗口 30 帧，量纲是**处理吞吐能力**（fps 当量），与相机到达率无关；同日志 `RATE arrive=29.7~30.8` 证明相机仍 ~30 | **确证**（代码+日志交叉） |
| 1b | 是否构成「>30 fps 曾真实发生」 | 不构成。是观测口径错误；既有笔记核心结论**不推翻** | **确证** |
| 2 | 官方文档面有无写给三方的 >30fps 预览/分析路径 | 无。camera 类 guide 对 慢动作/HIGH_FRAME_RATE/高帧率 **0 命中**；预览帧率文档只到 `getSupportedFrameRates()` | **确证**（语料穷举，负结论） |
| 3 | VideoSession 文档是否声明过 60fps | 有，但只针对**录像流**：「支持…可选择不同帧率（如30fps、60fps）」——预览/分析流无此声明 | **确证**（声明存在）/ 待验证（真机可否兑现） |
| 4 | 双流（preview+video）帧率协商规则 | 官方成文：录像流范围帧率→预览流必须**相同**范围；录像流固定帧率→预览流设其**约数**且必须也固定 | **确证**（文档原文） |
| 5 | NDK / MetadataOutput / Deferred / 双路预览 | 逐一排除：NDK 帧率面与 ArkTS 等价；MetadataOutput 只出人脸/人体矩形；Deferred 是拍照路径；双路预览只是两个 PreviewOutput | **确证** |
| 6 | 华为扩展 API（HMS/CollaborationCamera/GameService） | 均不提供 >30fps 三方相机流：CollaborationCamera 是跨设备调用（已废弃）；GameService 帧率是**渲染**帧率 | **确证**（文档面） |
| 7 | AVScreenCapture / DisplaySync 绕过 | 机制上**不能**突破：录屏采集的是屏幕内容，预览本身 30fps → 60fps 录屏只是重复帧；DisplaySync 管自绘 vsync，与相机输入无关 | **确证**（机制层） |
| ★ | 本轮唯一可行动增量 | 真机验证：`NORMAL_VIDEO` 会话 + 60fps videoProfile，按双流规则让 preview 跟设 60-60，**用 `RATE arrive=` 判定** | **待验证** |

---

## 二、逐题作答

### 第 a 题：`fps=43~58` 反常行的完整解释

#### a.1 这行日志是怎么算出来的（代码级）

日志产生方是 `<PRIOR_WORK>/lpr-harmony\LprDemo\entry\src\main\ets\pages\CameraPage.ets`
（应用包名 `com.shusen.lprdemo`，与 hilog 中的 tag `LprCamera` 一致）：

```ts
// CameraPage.ets L941-945
if (this.frames % 30 === 0) {
  hilog.info(DOMAIN, TAG,
    'FRAME n=%{public}d fps=%{public}s plate=%{public}s split=%{public}s',
    this.frames, (1000 / f).toFixed(2), this.plate, this.split.join('|'));
}
```

其中 `f` 来自 **L918**：`const f: number = p50(this.frameMsWin);`，而
`frameMs` 在 **L859-860** 定义：`frameMs = decodeMs + inferMs`，即
**JS 取帧/拷贝（prepMs）+ native 推理一轮（roundMs）的单帧处理耗时**；
窗口是 **L119** 的 `WINDOW = 30` 帧的滑动 p50。

> 所以 `FRAME fps` 的准确语义是：**假如帧不要钱，流水线每秒能处理多少帧**
> （= 1000 / p50(处理耗时)）。它是**产能**指标，不是**到达**指标。

#### a.2 数字交叉验证（不是巧合）

| 日志行（hilog_recovered.txt） | FRAME fps | 反推 p50 | 同窗口 STAGE conv+infer | 吻合 |
|---|---|---|---|---|
| :45 `FRAME n=240 fps=58.82` | 58.82 | **17.0 ms** | :37 `conv=5.3800 infer=11.5984` = **16.98 ms** | ✅ |
| :38 `FRAME n=30 fps=50.00` | 50.00 | 20.0 ms | （p50 略低于逐条 STAGE 值，同量级） | ✅ |
| :9 `FRAME n=30 fps=29.41` | 29.41 | **34.0 ms** | （早期窗口，处理更慢） | ✅ |

`fps=58.82` 那一刻，相邻 `STAGE n=240` 报的单帧处理耗时 5.38+11.60=16.98 ms，
1000/16.98 = **58.89**，与 58.82 在 p50 平滑误差内完全一致。

#### a.3 真正的到达率口径在同一段日志里，恰好是 ~30

到达率的唯一权威口径是 `RATE arrive=` 行（CameraPage.ets **L899-916**）：
`arrFps = arrivedInWin * 1000 / winMs`，其中 `arrivedInWin` 在 **`imageArrival`
回调**里计数（L717，注释 L712「每一帧都记到达（**包括被丢的**）」），
`winMs` 是**真实墙钟**（≥2000 ms 才结算，L904）。

`hilog_recovered.txt` 同一次采集里所有 RATE 行：

- :2（hilog.477）`arrive=30.59 done=27.63 dropped_in_win=5 gear=0`
- :25（hilog.478，gear=1）`arrive=30.82 done=30.32 dropped_in_win=0`
- :26 `arrive=29.69`、:27 `arrive=29.99`、:28 `arrive=30.14`

**相机到达率 29.7~30.8 fps，无一越界。** 而 `FRAME fps=43~58` 全部出现在
hilog.479（gear=1，处理已热身），同期到达率就是上面那几行 ~30。

补充机理：`finishFrame()`（L748-756 注释）故意设计成「算完立刻接手缓冲里的帧」，
使完成速率 ≈ 1000/工作耗时——这正是 `FRAME fps` 会系统性**高于**到达率的原因：
它衡量的是我们的处理能力，不是相机的产出。

#### a.4 判定

**观测口径错误，不构成「>30 fps 曾真实发生」的证据。既有笔记核心结论不推翻。**
（确证：代码定义 + 数字反推 + 同段日志到达率三重互证。）

防复发建议（给后续实验协议）：帧率类结论**只允许引用 `RATE arrive=` 行**；
`FRAME fps` 建议改名为 `capacity` 或在日志串里并写 `arrive=`，避免下一次再被读错。

---

### 第 b 题：官方文档面穷举（HuaweiDocs 全语料）

检索词与命中范围（对 `harmonyos-guides\*.md` + `harmonyos-references\*.md` 全量）：

| 检索词 | camera 类命中 | 备注 |
|---|---|---|
| `慢动作` / `SLOW_MOTION` / `HIGH_FRAME_RATE` | **0** | camera-*.md 全部 0 命中 |
| `高帧率` | **0**（camera 语境） | 命中的是 graphics/gameservice/pen 等非相机页 |
| `60fps` / `60 fps` | `arkts-apis-camera-videosession.md`（见下） | 唯一相机语境命中 |
| `setFrameRate` / `FrameRateRange` | camera-framerate / camera-setframerate-native / camera-preview / camera-recording / camera-concurrent-open + 对应 reference 页 | 均已知或下述 |

逐页结论：

1. **camera-framerate.md（已知）**：约束与限制仅一句「支持的帧率范围…依赖于硬件能力的实现」
   （L19）；`setFrameRate` 调用限制在 L96-99（旧笔记已引）。无任何 >30 承诺。
2. **camera-setframerate-native.md（已知）**：L33 同款「仅 NORMAL_PHOTO/NORMAL_VIDEO 支持调整预览流帧率」。
3. **camera-preview.md L518-535「设置预览帧率」**：只示范 `getSupportedFrameRates()` →
   `setFrameRate()` 动态调整，**没有列出任何具体数值范围**。
4. **【新增】arkts-apis-camera-videosession.md L17**：
   > 默认的视频录制模式…支持720P、1080p等多种分辨率的录制，**可选择不同帧率（如30fps、60fps）**。

   这是全语料中**唯一**一句把 60fps 写在相机文档里的声明，且明确限定于**录像**（VideoOutput），
   不是预览/分析流。
5. **【新增】camera-recording.md L55-78**：录像流帧率通过 `CameraOutputCapability.videoProfiles`
   的 `VideoProfile.frameRateRange` 选择（L55）；并给出**双流帧率耦合规则**（见第 c.6 条）。
6. **camera-api-faq.md / camera-previewoutput-faq.md / camera-dual-channel-preview.md**：
   帧率关键词 0 命中。

**结论：官方没有任何一条写给三方的 >30 fps 预览/分析流路径。**（确证·负结论，语料级穷举）

---

### 第 c 题：API 面增量逐项

#### c.1 VideoSession 下 preview profile 的帧率集合是否与 PhotoSession 不同

无新证据，维持旧笔记的源码级判断：profile 集合按 `session->GetMode()` 从
`camera_manager.cpp` 的**按 mode 缓存**里取（旧笔记 `preview_output.cpp` L494、
`camera_manager.cpp` L2651-2656），两套列表可能不同但同源于 HAL 元数据。
**待验证**（真机 A/B 仍未做）。

#### c.2 用 `OH_Camera**` NDK 直接建 Session

`<SDK>/...\ohcamera\camera.h` L165-180：`Camera_SceneMode` 只有
`NORMAL_PHOTO=1 / NORMAL_VIDEO=2 / SECURE_PHOTO=12` —— 与 ArkTS 完全一致。
`preview_output.h` L269/L283/L297 与 `video_output.h` L265/L292/L306 的帧率三件套
（GetSupportedFrameRates / SetFrameRate / GetActiveFrameRate）逐函数对应 ArkTS。
**确证：NDK 无增量。**（与旧笔记第 3 题一致，本轮在本地头文件复核。）

#### c.3 MetadataOutput

本地 `.d.ts`（`@ohos.multimedia.camera.d.ts`）L8893 起 `enum MetadataObjectType` **只有**
`FACE_DETECTION=0`、`HUMAN_BODY=1`；输出的是 `Rect` 检测框元数据（L9017-9031），
**没有任何图像数据通路**。**确证：与帧率无关，不可用。**

#### c.4 defer image / DeferredImageDelivery

- `createDeferredPreviewOutput(profile)`（.d.ts L1194-1204）：只是**延迟绑定 surface** 的
  PreviewOutput 创建方式，帧率语义无差别。
- deferred photo delivery（L7839-7855）：**拍照**路径的快速出图（先低质后高质），
  与预览/分析流帧率无关。
**确证：两者都不是 >30fps 路径。**

#### c.5 ImageReceiver 尺寸/格式（YUV vs RGBA）对 profile fps_ 的影响

旧笔记已确证 profile 是 **per format+size** 的，`getSupportedFrameRates()` 先按
format+宽高精确匹配再取 `fps_` 去重。增量排查结果：**文档与 .d.ts 都没有给出
任意 (format,size) → fps 的映射表**；`60-60` 挂在哪个三元组上仍只能靠设备
`DumpProfile` hilog（需开 debug 级别日志）。
**待验证**（方法：换 YUV/RGBA、640x480/960x960 等组合建 output，逐个读 `getSupportedFrameRates()`）。

#### c.6 双流（preview+video）帧率协商规则 —— 【本轮最重要增量】

`camera-recording.md` L74-78（原文）：

> - 在设置预览流帧率时，需要先通过 getActiveFrameRate 查询当前**录像流**的帧率。
> - 当录像流已设置过**范围帧率**时，预览流帧率必须设置**与其相同的范围帧率**。
> - 当录像流已设置过**固定帧率**时，预览流帧率要设置成**录像帧率的约数**，且必须也为固定帧率。

含义：**预览流帧率不是独立的，它被录像流的档位约束**。若录像流能设 60-60
（videosession 文档 L17 声明支持），则预览流可设 60-60（相同范围帧率）。
这给了一条文档面上成立的、此前没试过的组合：

> `createSession(NORMAL_VIDEO)` + `createVideoOutput(60fps videoProfile)` +
> 预览/分析流 `setFrameRate(60,60)`，判定用 `RATE arrive=`。

**待验证**（本 SKU 是否兑现 60fps 录像档未知；且 daemon `setMaxFps` 从不超 30 的
观测提示大概率仍被钳位，但这是唯一没被真机证伪的官方路径）。

#### c.7 `SceneMode.NORMAL_VIDEO` 下请求 60

与 c.6 同一条路的单流版本：NORMAL_VIDEO 会话下预览流直接 `setFrameRate(60,60)`。
源码级推断与 NORMAL_PHOTO 无差（同 HAL 声明），文档面无预览 60fps 声明。
**待验证**（优先级低于 c.6，因为 c.6 至少有录像 60fps 的文档声明兜底）。

---

### 第 d 题：华为设备特有扩展 API

对语料检索 `CollaborationCamera`、`GameService`、`高帧率`、`慢动作` 的结论：

1. **CollaborationCamera**（servicecollaboration-collaborationcamera.md）：
   跨设备互传组件——「在 PC/2in1 端跨端调用 Phone 端拍照」，**且自 5.0.0(12) 起已废弃**，
   被 CollaborationService 取代。与帧率无关。
2. **GameService GamePerformance**（gameservice-gameperformance.md L122-156）：
   `maxFrameRate` / `currentFrameRate`（取值 [1,144]）/ `recommendedFps` ——
   管的是**游戏渲染**帧率（控帧系统对 UI/渲染的 vsync 分发），不是相机输入流。
3. 语料内**没有任何** HMS Camera Kit 扩展页声明给三方 >30fps 相机流
   （`高帧率`/`慢动作`/`HIGH_FRAME_RATE` 在 camera 语境 0 命中）。

**结论：未发现华为扩展 API 能给三方 >30fps。**（确证·文档面穷举的负结论）

---

### 第 e 题：绕过路径（机制与限制）

#### e.1 AVScreenCapture（录屏取帧）

官方口径：

- `OH_AVScreenCapture_SetMaxVideoFrameRate()`：**「当前支持的最高帧率为60FPS，
  当入参设置超过60FPS，将以60FPS处理」「实际帧率受设备能力限制」**
  （capi-native-avscreen-capture-h.md L62、L855）。
- 取原始帧的通路存在：`OH_AVScreenCapture_OnBufferAvailable` 回调里
  `OH_SCREEN_CAPTURE_BUFFERTYPE_VIDEO = 0` 可拿到视频缓冲
  （capi-native-avscreen-capture-base-h.md L296、L534）；Surface 模式
  `OH_AVScreenCapture_StartScreenCaptureWithSurface()`（avscreencapture-screen-recording-c.md L617/L654，
  帧格式 `OH_VIDEO_SOURCE_SURFACE_RGBA`，L204/L824）。

但**机制上它不是相机帧率绕过**：录屏采集的是**屏幕内容**。
相机预览本身被钳在 30fps → 屏幕每秒只有 30 个新画面，60fps 录屏只会得到
每帧重复两次的序列；传感器出帧上限原样传导。附加代价：录屏隐私告警弹窗
（免弹窗的 `ohos.permission.CUSTOM_SCREEN_RECORDING` 仅 PC/2in1 且 API 22 起，
using-avscreencapture-arkts.md L35）、写文件模式「无法获取原始数据码流」
（avscreencapture-screen-recording-c.md L31，须走 Surface/Buffer 模式）。

**结论：不可行（对提升相机帧率而言）。确证·机制层。**

#### e.2 DisplaySync / DisplaySoloist / NativeVsync

可变帧率体系管的是**自绘内容的 vsync 分发**（动画/UI/XComponent 自绘/非 UI 线程绘制，
displaysync-overview.md），且文档明确「开发者设置的期望帧率值**不能代表**最终实际效果，
会受限…屏幕刷新率硬件能力限制」。与相机输入流的帧率无交集。
**结论：不可行。确证·机制层。**

#### e.3 综合判定

30 fps 是本 SKU 相机侧的应用可见硬上限，**不存在官方替代取流方式能提升传感器出帧**。
能提高的只有**处理吞吐**——而日志已证明流水线产能（43~58 fps 当量）本来就高于
相机供给（~30），瓶颈始终在相机侧。

---

## 三、边界与未验证

### 3.1 无法获取（硬边界）

1. HAL 元数据里 `60-60` 档位挂载的 (format, size, fps) 三元组 —— 只能靠真机
   DumpProfile hilog（debug 级），设备外不可得。
2. 厂商 daemon `setMaxFps` 的钳位逻辑（本轮 hilog.477/479 中再次出现
   `setMaxFps … now setlimit[%d] fps=%d` 字样，hilog_recovered.txt L20-23，
   与旧笔记 `Misc.cpp:4026` 侧证一致，仍为闭源）。

### 3.2 未验证推断（含证伪方法）

| 推断 | 依据 | 证伪/验证方法 |
|---|---|---|
| NORMAL_VIDEO + 60fps videoProfile + preview 60-60 能跑通双流配置但到达率仍 ~30 | camera-recording.md L74-78 + videosession L17 声明；daemon 钳位先验 | 真机：建 NORMAL_VIDEO 会话→addOutput(video+preview+receiver)→videoOutput.setFrameRate(60,60)→preview setFrameRate(60,60)→只看 `RATE arrive=`。若 arrive>30 → 推翻旧笔记；预期 arrive≈30 |
| 不同 (format,size) 下 `getSupportedFrameRates()` 返回不同 | 旧笔记确证 profile per format+size | 真机遍历 YUV/RGBA × {640x480, 960x960, 1280x720} 逐个读列表 |
| VideoSession 的 preview profile 集合 ≠ PhotoSession | 源码按 mode 取缓存 | 真机 A/B 打印两模式列表 |

### 3.3 方法论说明

- 本轮语料检索为**子串穷举**（`Select-String -SimpleMatch`，词表见第 b 题），
  覆盖 `harmonyos-guides` + `harmonyos-references` 全部 .md；未做语义检索，
  不排除个别同义表述（如「高刷」）漏网 —— 但相机语境下主词已覆盖。
- hilog_recovered.txt 是从损坏的 hilog gzip 中恢复的**混叠文本**（App 行与系统行交错），
  行号以恢复文件为准；App 侧日志口径以 CameraPage.ets 源码为准（一手）。
- 引用文件清单：`<PRIOR_WORK>/lpr-harmony\LprDemo\entry\src\main\ets\pages\CameraPage.ets`、
  `<SDK>/openharmony\ets\api\@ohos.multimedia.camera.d.ts`、
  `<SDK>/openharmony\native\sysroot\usr\include\ohcamera\{camera,preview_output,video_output}.h`、
  `<DOCS_CORPUS>\cn\harmonyos-guides\` 下 camera-framerate / camera-preview /
  camera-recording / camera-setframerate-native / avscreencapture-screen-recording-c /
  using-avscreencapture-arkts / displaysync-overview 各 .md、
  `<DOCS_CORPUS>\cn\harmonyos-references\` 下 arkts-apis-camera-videosession /
  gameservice-gameperformance / servicecollaboration-collaborationcamera /
  capi-native-avscreen-capture-h / capi-native-avscreen-capture-base-h 各 .md、
  `<REPO>/lpr-kirin8020\_scratch\hilog_recovered.txt`。

---

## 四、【2026-09-21 真机复测】3.2 第一行**被推翻**：耦合双流路径真实兑现 60fps

**时间**：2026-09-21 14:23–14:32 · **热档 3**（电池 41 ℃）· release 构建（`check_native_build_flags.py` 通过，-O2）
**应用侧**：`lpr-kirin8020-app` commit `c1ed5d6` —— CameraPage.ets 新增档 5「视频60」
（NORMAL_VIDEO 会话 + 预览/分析流 `setFrameRate(60,60)`）与档 6「视频+录」
（再加 `VideoOutput(480x480@60-60)`，AVRecorder 供 surface，按耦合规则配置）。
两档均只取帧不推理（基准档仪器族），判定只用 `RATE arrive=`（2 s 窗、45 s 稳态门）。

### 4.1 结果（app 仓库 `evidence/video60_gear5_gear6.runlog`，n=RATE 窗口数）

| 档 | 会话 | 请求 | arrive min~max | mean | 丢帧 |
|---|---|---|---|---|---|
| 3 基准（对照） | NORMAL_PHOTO | 30-30 | 29.76~30.24 | **30.01**（n=34） | 0 |
| 5 视频·单流 | NORMAL_VIDEO | 预览 60-60 | 25.57~26.50 | **25.98**（n=62） | 0 |
| **6 视频+录（双流）** | NORMAL_VIDEO | 预览 60-60 + 录像 60-60 | **39.01~58.35** | **47.15**（n=90，含爬坡） | **0** |

档 6 后段窗口稳定在 **56~58.35 fps**（≈60 减去消费侧开销）。**>30 fps 的预览帧第一次真实到达。**

### 4.2 同时钉死的两个旧未验证项

1. **§3.1-1**（fps 三元组）：档 5/6 起流时全量 dump 了 NORMAL_VIDEO 的录像 profile
   （hilog `VIDPROFILES[0..6]`，证据 `evidence/video60.hilog.txt`，在 app 仓库）——
   **每个 size 都有 `YUV420SP(1003)@60-60` 固定帧率档**（另有两路 `@1-30`），
   最小 480x480，640x480 也有 60-60。`60-60` 不是单条孤立声明，是**覆盖全尺寸的一族**。
2. **前序笔记 §4.2-3**：NORMAL_VIDEO 的**预览** profile 集合与 NORMAL_PHOTO 相同
   （两模式 `FPS RANGES` 均为 `[1-30, 60-60]`）——差异不在预览 profile，在**录像流的配置**。

### 4.3 被推翻的结论（明确标注）

- `camera-fps-ceiling.md`「30 fps 是相机侧硬上限」——**推翻**。30 fps 是
  **「预览/分析-only 配置」下的钳位值**；一旦会话里存在固定 60-60 的录像流
  （耦合规则），预览流跟随进入 60fps 模式，到达 56~58。
- `camera-60fps-research.md` ★ 行「daemon `setMaxFps` 从不把上限抬到 30 以上」——
  **在该配置组合下不成立**。钳位是**条件性**的，条件就是双流配置。
- 「`60-60` 被接受但不兑现」的旧实测仍然成立——**仅限无 VideoOutput 的配置**
  （本轮档 5 复现为 ~26，甚至低于 30）。

### 4.4 新边界与未验证（下一轮）

1. **机理是行为推断**：本轮 hilog 缓冲里没有抓到 daemon `setMaxFps` 行（环形缓冲滚掉），
   「录像流触发 60fps 传感器档」是从配置-行为对应得出的，**未读到钳位代码**（不做逆向，立场同 ADR-0003）。
2. **mp4 只有 44 字节**：AVRecorder start 成功但编码产物几乎为空 —— 录像路**帧是否真正
   被编码器消费**未验证。到达率仪器数的是**分析流**的 `imageArrival` + 真实
   `readLatestImage` 消费，不受此影响；但这意味着「录像流必须真实出帧」是否为触发条件**存疑**
   （也可能仅建流/配置即可）。mp4 留在设备 `files/video60_*.mp4` 可复查。
3. **稳态时长未测**：观测仅 ~4 min；更长时间与更高热档下的稳定性、以及 60fps 模式是否回退未知。
4. **流水线产能成为新瓶颈**：帧预算从 33.3 ms 变 16.7 ms，而检出帧 native ~40 ms /
   全 NPU ~28 ms —— **到达 60 ≠ 完成 60**。RQ3/RQ4 的既有数据全部是 30 fps 到达率下采集的，
   仍然有效；若要跑 60fps 场景，检测段落点问题**重新变成主矛盾**。
5. **判据纪律不变**：本轮全部结论基于 `RATE arrive=`（真回调 + 墙钟），
   `getActiveFrameRate()` 在三档里都只回报协商值（30-30/60-60），依旧不可信。
