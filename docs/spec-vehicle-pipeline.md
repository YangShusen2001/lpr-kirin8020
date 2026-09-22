# Spec · 车辆识别流水线（相机实时 + 截 ROI 检测识别）

- **日期**：2026-09-22
- **状态**：已确认（用户 2026-09-22 回「做」）。**T1 已完成** —— 见
  [issue #29](https://github.com/YangShusen2001/lpr-kirin8020/issues/29)（真机验证证据在票上）
- **前置**：`docs/notes/vehicle-detection-pipeline-research.md`（实测证据全在此）
- **ADR**：ADR-0005（颜色用像素测量）、ADR-0008（探针台 UI；§6 相机线已部分推翻，见其修订附录）、ADR-0009（真机装机）

## 一、目标

在真机上做成一条**能实时跑、看得见**的车辆识别流水线，用于求职作品集演示：

> 相机画面 → **车辆检测** → **截取 ROI** → 车牌检测 → 矫正 → 识别 + 颜色（蓝/绿/黄）

用户原话：

> "还有我想做一个车辆识别的。车辆检测--->截取ROI区域--->车牌检测--->车牌识别+颜色"
> "这是因为数据集的关系，我用摄像头去实时用的时候会用到，因为干扰多，得放大来看"
> "我是说得截取ROI来检测识别"
> "恢复相机实时"

## 二、范围

### 做

| # | 内容 | 理由 |
|---|---|---|
| 1 | **恢复相机实时页**，双路预览（显示 + 分析） | 用户明确要求；`CameraPage.ets` 在 HEAD 里可复用 |
| 2 | **车辆检测**（新增环节，项目目前没有） | 用户要的核心新功能 |
| 3 | **ROI 路径**：整车 → 车框 → 裁 ROI → 车牌检测 | 用户坚持的设计 |
| 4 | 车牌识别 + 颜色（复用现状） | 已有能力，不重做 |
| 5 | 可视化：车辆框 + 车牌框 + 车牌串 + 颜色 | 作品集的「看得见」 |
| 6 | **对照开关**：ROI 路径 vs 全图直检，可在界面切换 | 探针台的价值就是能对比；也是本项目的证据文化 |

### 不做

| 不做 | 理由 |
|---|---|
| 自训练车辆检测模型 | 用户定：「下载别人的模型，做演示」；CCPD 无车辆框标注 |
| 声称车辆检测的 mAP | **没有车辆 GT**，任何精度数字都不成立（研究笔记 §7.1） |
| 车身颜色识别 | 用户已定：颜色指**车牌**颜色（ADR-0005 口径） |
| 交互式手动框选放大 | 用户明确否掉（「我是说得截取ROI来检测识别」） |
| 用 CCPD 证明 ROI 有收益 | **该数据集上直检 100% 召回，结构上无法证明**（研究笔记 §5.7） |

## 三、架构

```
相机 PreviewOutput#2 ─→ ImageReceiver(JPEG) ─→ RGBA
                                                  │
                    ┌─────────────────────────────┴──────────┐
                    │                                        │
              [ROI 路径]（用户要的，可开关）            [直检路径]（对照，可开关）
                    │                                        │
        ┌───────────▼───────────┐                   ┌────────▼────────┐
        │ 车辆检测（新增）       │                   │ 车牌检测         │
        │  · conf=0.05（低阈值） │                   │  y5fu_320x      │
        │  · 遍历所有框          │                   │  （全图 letterbox）│
        └───────────┬───────────┘                   └────────┬────────┘
                    │ 车辆框 N 个                            │ 车牌框
        ┌───────────▼───────────┐                            │
        │ 逐框裁剪 ROI（外扩15%）│                            │
        │  → 车牌检测（每框一次）│                            │
        │  → 框映射回原图坐标    │                            │
        └───────────┬───────────┘                            │
                    │                                        │
                    └───────────────┬────────────────────────┘
                                    ▼
                        合并去重（按 IoU）→ 矫正 → 裁切
                                    ▼
                        识别（rpv3）+ 颜色（像素测量）
                                    ▼
                        车辆框 + 车牌框 + 车牌串 + 颜色
```

### 关键设计决定

**D1 · 车辆检测用低置信阈值（0.05），且遍历所有车框。**
不是可选优化，是**必做**。实测这两条把 ROI 路召回从 82.5% 拉到 **91.0%**（+8.5pp）。
理由：ROI 前置里车辆检测器的目标是**召回**而非 mAP ——
多框只多跑几次车牌检测，漏检则召回归零。（研究笔记 §5.8）

**D2 · 两条路径都保留，界面可切。**
ROI 路径在 CCPD 上实测 −9.0%，但用户真实场景（远距离、多干扰）**未被覆盖**。
保留直检路径既是对照，也是真实场景下的安全网。

**D3 · 合并去重必须做。**
遍历所有车框会产生**重叠车牌框**（同一块牌被两个车框各检出一次）。
按 IoU 去重（阈值 0.5）+ 按分数排序保留最高分，避免同一块牌输出两行结果。

## 四、相机恢复方案

`CameraPage.ets`（2140 行）**仍在 git HEAD 里**（上一轮的删除尚未提交）。它已包含本项目
在相机上踩过的全部坑，**直接恢复+改造，不要重写**：

| 已有能力 | 为什么必须复用 |
|---|---|
| 双路预览（PreviewOutput#1 显示 / #2 分析） | 官方《实现自定义相机》双路预览模式 |
| JPEG 取帧路径（非 YUV） | 走系统解码器出 RGBA，少一段自研代码 = 少一个精度争议点 |
| 计时口径分离（decodeMs / inferMs / frameMs） | CONTEXT.md 规定：服务时间 ≠ fps，不能混 |
| p50 **按是否检出分桶** | 未检出帧便宜得多，不分桶就是两种分布的混合（实测 20.30 vs 30.32 ms） |
| 丢帧策略（不排队） | 测的是"这条流水线能跑多快"，不是输入帧率 |
| 档位机制（生产档 / NPU 档 / GPU 档） | 一次只切一件事，差异只能来自后端 |
| 权限 / 生命周期 / 热态电池探针 | 相机页特有，重写必踩 |

### 改造点

1. 新增**车辆检测**环节与两条路径的切换。
2. 结果区增加**车辆框**与**车牌→车辆归属**。
3. `Index.ets`（离线探针台）的入口加一个「相机」按钮 ——
   注意 `main_pages.json` / `module.json5` / `string.json` 的相机残留也要一并恢复。

## 五、车辆检测模型

### 现状

- 项目**没有任何车辆检测模型**（研究笔记 §2）。
- 已导出 `_veh/yolov5su_320.onnx`（ultralytics v5-u，**含 DFL**）。

### 上 NPU 的前置任务

v5-u 的 DFL 正是 YOLOv8 失败的同一根源（`/model.24/dfl/Transpose perm=[0,3,1,2]`）。
上 NPU 前**必须先换原版 anchor-based YOLOv5**（与现有 `y5fu_320x_head` 同架构），
并用 `tools/scan_onnx.py` 静态扫描确认两条硬门：
① 所有张量 rank ≤ 4 ② Transpose perm 只允许 `[0,1,3,2]`。

### 建议的落地顺序

| 阶段 | 后端 | 理由 |
|---|---|---|
| **一期** | **ncnn（CPU）** | 复用现有管线；相机场景延迟敏感；不必先解决 YOLOv5 导出与 NPU 转换 |
| 二期 | .ms（NPU） | 换原版 YOLOv5 → 裁 decode 到 rank-4 → 转换；符合项目 NPU 主题 |

**一期先用 ncnn 把端到端跑通**，NPU 作为独立一轮（它有自己的转换风险，不该阻塞主链路）。

### 许可

YOLOv5 是 **AGPL-3.0**。权重入库需标注许可，公开作品集仓库须说明来源。
`tools/scan_for_publication.py` 会扫这类资产 —— 提交前必跑。

## 六、ROI 路径实现要点

1. **裁剪位置**：优先在 **native 侧**完成（避免 RGBA 大 buffer 跨边界多次拷贝）。
   若一期为求快在 ArkTS 侧裁，必须记录这条取舍及其代价。
2. **外扩比例**：0.15 起（实测 0.15 与 0.40 差异 <1%，取小者省像素）。
3. **坐标映射**：ROI 内检出的框必须映射回原图坐标后再参与去重与可视化，
   否则界面上的车牌框会画在错误位置。
4. **线程契约**：全部走 `*Async`。`lpr.*` 同步版本阻塞 UI 线程 >3s/>6s 会被
   watchdog 判 `THREAD_BLOCK` 并 SIGKILL。
5. **会话名**：传**模型文件路径**（原生侧按 `(name|backend)` 去重）。

## 七、验收标准

| # | 标准 | 判据 |
|---|---|---|
| A1 | 相机实时出结果 | 真机（`MIA-AL00`）上看到车辆框 + 车牌框 + 车牌串 + 颜色 |
| A2 | 两条路径可切 | ROI / 直检切换后，结果区与耗时统计随之变化 |
| A3 | 车辆检测用 conf=0.05 且遍历所有框 | 代码可查；日志打印车框数 |
| A4 | 计时口径合规 | 报 `frameMs` 与「余量 = 33.3 − frameMs」，**不得把 `1000/p50` 称作 fps** |
| A5 | p50 按是否检出分桶 | 沿用 `CameraPage` 既有实现 |
| A6 | 门禁 | `verify_published_numbers.py` **67/67**；`scan_for_publication.py` **0 阻断** |
| A7 | 不回归 | 现有离线探针台功能不受影响 |
| A8 | 诚实标注 | 界面与文档**不得**声称车辆检测精度；ROI 收益必须标注「本数据集上为负，待真实素材验证」 |

## 八、风险与未决

1. **ROI 路径在真实场景是否划算是未知的** —— 这是本 spec 最大的不确定性。
   CCPD 上它 −9.0%；真实场景（远距离、多车、强干扰）未被覆盖。
   **缓解**：保留直检路径（D2），并把两条路径的**线上对比**做进界面 ——
   真机跑起来后，真实素材上的对比数据会自己长出来。
2. **车辆检测器仍是瓶颈**：剩余 9.0% 差距里 7.5% 来自「车辆完全检不出」。
   一期用通用 COCO 模型无法解决；二期若换更强的车辆检测器需重跑研究笔记里的实验。
3. **相机权限与真机可用性**：云手机**不支持相机**（研究笔记环境约束），
   验证必须在物理真机 `MIA-AL00` 上做。
4. **端侧性能未知**：车辆检测（1 次）+ 车牌检测（N 次，N=车框数）在相机帧预算
   （33.3 ms）内的开销**未实测**。若超预算，需要降分辨率或减少 ROI 数。
5. **AGPL-3.0 许可**（见 §5）。

## 九、拆分（to-tickets 的输入）

| # | 工单 | 依赖 |
|---|---|---|
| T1 | 恢复 `CameraPage.ets` 与相机相关配置（不改造，先跑通原功能） | — |
| T2 | 车辆检测 ONNX → **.ms** 转换 + 端侧接口（`vehicleDetectAsync`） | — |
| T3 | native/ArkTS 侧 ROI 裁剪 + 坐标映射 | T2 |
| T4 | ROI 路径串联（车框 → 逐框车牌检测 → 合并去重） | T2, T3 |
| T5 | 界面：车辆框 + 车牌→车辆归属 + 两路径切换 | T1, T4 |
| T6 | 真机端到端验证 + 计时/性能实测（A1–A5） | T5 |
| T7 | 门禁 + 许可标注（A6, A8） | 全部 |
| T8 | 换原版 anchor-based YOLOv5 + NPU 转换（二期，独立） | — |

## 九·补、T2 实施记录与路线修订（2026-09-22）

### 修订 1：T2 的转换目标由 **ncnn** 改为 **MindSpore Lite `.ms`**

票面原写「车辆检测 ONNX → ncnn 转换 + 端侧接口」。实施时摸排发现两件事，
路线因此改掉，且**不是偏好问题**：

1. **本项目的 CPU 通路本来就是 MS Lite + `.ms`**。`LprSessions::det` 走的是
   `y5fu_320x_head_fp32.ms`，而且它**本来就在 CPU**（ADR-004 §4.1：NPU 判否）。
   ncnn 在本项目只服务 GPU/Vulkan 档（ADR-008）。为 T2 一期新引入 ncnn
   等于**多一条并行通路要维护**，而不是「复用现成通路」。
2. **真正的障碍是 DFL，它对两条路线都挡**。`yolov5su`（YOLOv5u/ultralytics）的
   DFL 头里有两个 `perm != [0,1,3,2]` 的 Transpose：

   | 节点 | perm |
   |---|---|
   | `/model.24/dfl/Transpose` | `[0,3,1,2]` |
   | `/model.24/dfl/Transpose_1` | `[0,3,2,1]` |

   MindSpore Lite 的 `InferShapeByNNACL` 直接在 `/model.24/dfl/conv/Conv` 上失败
   （`Transform meta graph failed! ret = -500`），**连 CPU 的 `.ms` 都产不出来**；
   `tools/scan_onnx.py` 独立印证同一处（两条 NPU 硬门的第 2 条）。

   所以无论走 ncnn 还是 `.ms`，DFL 都得先改写 —— 这是先决条件，不是路线分歧。

**修订后的路线**：改写 DFL → 转 `.ms` → 走已有的 MS Lite CPU 通路。
与现有 `det=CPU` 完全一致；且 DFL 里的两个 Transpose 一并消失，
**T8 的 NPU perm 硬门也顺带清了**（`scan_onnx.py` 由「2 个 NOT SUPPORTED」变为 0）。

### 改写怎么做：`_veh/patch_dfl.py`

DFL 的数学是「对 16 个 bin 做 softmax，再按 0..15 加权求和」，两个 Transpose 只是
把待归一化的轴搬到最后一维的搬运工。改写采用**最小差分**：

- 删 4 个节点：`Transpose` / `Softmax` / `Transpose_1` / `conv/Conv`
- 加 7 个节点：`ReduceMax → Sub → Exp → Mul(bins=arange(16)) → ReduceSum(分子)
  → ReduceSum(分母) → Div`
- 只重接 1 处输入：`/model.24/dfl/Reshape_1` 的 input[0]

保留 `Reshape_1` 不动 ⇒ 最终张量名 `/model.24/dfl/Reshape_1_output_0` 不变，
它的 3 个消费者（`Shape` / `Slice` / `Slice_1`）一个都不用碰，
输出 `output0 [1,84,2100]` **格式不变**。

### 三个必须记下来的坑

1. **opset ≤ 12 的 `Softmax` 是「coerced-2D」语义，不是「沿给定轴归一化」。**
   它把 `[0,axis)` 压成一维、`[axis,rank)` 压成另一维，对**后一维**做 softmax。
   在 `[1,4,16,2100]` 上写 `Softmax(axis=2)`，实际算的是「4 行 × 33600 的 softmax」——
   本机实测与正确结果差 **1.0**（完全错）。**这正是 ultralytics 当初非要插
   `Transpose[0,3,1,2]` 的原因**：opset 12 下只有把轴搬到最后一维才写得出 softmax。
   （opset 13 才改成沿轴语义。）⇒ 不用 `Softmax` 算子，改用手工形式。
2. **必须减最大值（`ReduceMax`/`Sub`）**。DFL 的 logits 后面没有激活函数压着，
   实测在 0..255 的随机图上**裸 `Exp` 直接溢出成 `inf`**，随后 `inf/inf = NaN`。
3. **自证门禁自己会撒谎**：`worst = max(worst, nan)` 在 Python 里返回 `worst`
   （因为 `nan > worst` 为假），于是「输出全是 NaN」会被**静默判成通过**。
   必须先查 `isfinite` 再比大小。这条比模型错误更危险 —— 是**验证工具**在骗人。

正确性判据不是「读图读对了」，而是**数值自证**：`patch_dfl.py` 用 onnxruntime 在
同一输入上跑原图与改后图，逐元素比对，判据是 `|a-b| ≤ 1e-6 + 1e-5·|a|`（3 个随机图）。
**不过就不落盘。** 实测归一化误差 0.18~0.22（预算 1.0，余量 5×）。

（另：判据**必须**用相对形式。`output0` 的 box 通道是像素量纲，box decode 会乘上
stride（最高 32），而 DFL 自身只有 0..15 的量级；手工 softmax 与算子 softmax 的
fp32 舍入差 ~4e-6 乘 stride 后就是 ~1.2e-4 —— 用绝对阈值会把纯浮点舍入误判成错误。）

### 端侧接口的验收口径（T2）

票面要求「PC 侧与 native 侧在同一张图上结果一致」。做法上有一处关键设计：

**测试图恰好取 320×320。** 源图等于 letterbox 目标尺寸时 `r=1`、`left=top=0`，
letterbox 退化成**逐字节拷贝** —— 两侧看到的模型输入是同一串字节，
把「两侧插值实现差异」这个不可控变量从等式里消掉，剩下的差异只可能来自解码。
（若源图尺寸不等于 320，native 的手写双线性与 PC 的 PIL 本来就不会逐位相同，
「结果不一致」会变成分不清是解码写错还是插值差异的糊涂账。）

对照工具：`_veh/veh_ref.py`（PC 侧参考解码 + 真机 hilog 解析 + 贪心配对比对）。
设备侧证据走 `hilog`（一行汇总 + **每框一行**，绕开单条 hilog 的长度上限），
不走 App 私有目录 —— 那个 hdc 拉不出来。

### 真机侧对照结果（2026-09-22，已完成）

真机 `MIA-AL00` / HarmonyOS 6.1.0.135 / API 24，
`LANDED=CPU`（`trail=[CPU(ok)]`，无回退）。

```
[veh_ref] 设备日志含 2 轮，取最后一轮；各轮框数 [5, 5]
[veh_ref] 各轮框逐元素一致：是（可复现）
[veh_ref] 设备: count=5 truncated=0 conf=0.050000 iou=0.500000 vehicleOnly=1 size=320 nhwc=1 inferMs=48.535469 backend=CPU
[veh_ref] PC  : count=5 truncated=False conf=0.0500 iou=0.5000 vehicle_only=True size=320

[veh_ref] 配对 5 / PC 5 / 设备 5
[veh_ref] 坐标最大偏差 = 0.0000 px（中位 0.0000）
[veh_ref] 分数最大偏差 = 1.73e-06（中位 7.26e-07）
[veh_ref] 最小配对 IOU   = 0.999998

[veh_ref] ✓ PC 与设备结果一致（数量、类别、坐标、分数都在容差内）
```

⇒ 票面「PC 侧与 native 侧在同一张图上结果一致」**达成**。
坐标偏差停在 fp32 舍入量级、分数偏差 1.7e-06，说明两侧差异**纯粹来自浮点**，
不含任何解码 / letterbox 层面的语义差异。

**门限为什么取 0.5 px / 1e-3**：实测值是 0.0000 px 与 1.73e-06，门限各留约 4 个数量级余量；
而一旦「通道优先 `raw[c*anchors + a]`」或 letterbox 反变换写错，框会**整体移位几十 px**，
绝不会停在 0.5 px 以内 —— 松到不误杀浮点噪声，紧到抓得住真错。

**顺带得到的两条证据**：
- 同一张图连跑两轮（预热 + 正式读）**逐元素一致** ⇒ 端侧推理可复现。
- 冷启动 `inferMs` 66.5 ms → 热态 48.5 ms（`totalMs` 69.1 → 49.6 ms），给 T6 的性能实测留了基线。

复现命令：

```
python _veh/veh_ref.py --compare --ref-json _veh/veh_ref.json --device-log _veh/devlog_VEH.txt
```

### 驱动与比对的坑（T2 实测踩到，已修进工具）

1. **锁屏判据不能用泛化的 `lock`。** 第一版把 `lock` 当锁屏标记，结果命中
   `ClockStatusView` / `clock_home_row` / `TextClock` —— **"Clock" 含 "lock"**，
   设备明明已解锁却被判 `LOCKED`。改用专有词（`Digital_PSD_Input` / `ScreenLock` / `未识别成功` …）。
   **真正的锁屏判据是布局树的 bundle 归属**：出现 `com.shusen.lprdemo` 就是在自己的 App 里；
   只有 `com.ohos.sceneboard` 才可能是锁屏或桌面。
2. **比对脚本必须按「轮」切日志。** App 是「预热一次 + 正式读一次」，hilog 里因此有
   **两整轮相同的框**。不切轮 → 同一批框被数成两批 → 贪心配对只消耗一半 →
   剩下一半被误报成「设备独有 5」，看起来像模型错，实际是解析错。
   修完后同一个日志从「✗ 设备独有 5」变成「✓ 5/5 全配对」。
3. **`--ref` 在 `veh_ref.py` 里是「产出参考」的布尔开关**，不是路径。
   待比对的参考文件走 `--ref-json`（默认 `_veh/veh_ref.json`）。早先 `cmd_compare`
   误把 `a.ref` 当路径 `open()`，是脚本自身的 bug，已修。

真机驱动统一走 `_veh/dev.py`（`state` / `layout` / `struct` / `start` / `tap` / `swipe` /
`log` / `logclear` / `ps`）—— 用 Python 取回 hdc 输出，避免 PowerShell 管道按遗留代码页
重解码中文。

### 已知未完成

- **`.ms` 的 PC 侧逐元素保真度没能验证**：MS Lite 自带的 `benchmark.exe` 能加载能跑
  （`PrepareTime ≈ 66–76 ms`），但它的 accuracy 对照是**按输出张量名**取数据的，
  本模型在 unified API 下 `GetOutputTensorNamesChar()` 返回**空名** ⇒
  `Model does not contains tensor .`，必然失败（换 `--modelType=MindIR_Lite` 也一样）。
  详见 `_veh/ms_fidelity_check.py` 的「实测结论」。⇒ 该项改由**真机侧**对照覆盖。
  顺带记录：黄金数据的 flag 是 `--benchmarkDataFile`（**不是** `calibDataFile`）。
- ~~**真机侧对照尚未执行**~~ → **已于 2026-09-22 完成**，见上「真机侧对照结果」。
  （当时卡点是设备处于数字 PIN 锁屏，`aa start` 报 `Error Code:10106102`；人工解锁后即跑通。）

### 已通过的门禁与产物

| 项 | 结果 |
|---|---|
| `_veh/patch_dfl.py` 数值自证 | ✓（归一化误差 0.18~0.22 / 预算 1.0） |
| `tools/scan_onnx.py`（改写后） | ✓ 两条硬门全过；Transpose 2 → **0** |
| `converter_lite --fp16=off` | ✓ `CONVERT RESULT SUCCESS:0`，36,675,600 B |
| PC 侧参考（`veh_ref.py --ref`） | ✓ 5 框，主检出 car@0.9355 |
| App 构建（native + ArkTS） | ✓ 无编译错误；`.so` 含 `LprVehicleDetect` / `vehicleDetectAsync` |
| 华为签名 | ✓ 信任根 `Huawei CBG Developer Relations CA G2` |
| 装机 | ✓ `install bundle successfully` |
| **真机侧对照（T2 票面验收）** | ✓ **5/5 全配对**；坐标最大偏差 0.0000 px、分数 1.73e-06、最小 IOU 0.999998 |
| 端侧可复现性 | ✓ 同图两轮推理逐元素一致 |
| `tools/verify_published_numbers.py` | ✓ 全部 67 项通过 |
| `tools/scan_for_publication.py` | ✓ 0 阻断（1 项文本待确认：论文里的联系邮箱） |

## 九·补二、T3 实施记录（2026-09-22）

### 做了什么

**native（`lpr_pipeline.{h,cpp}`）**

| 接口 | 作用 |
|---|---|
| `RoiRect` / `LprRoiFromBox(box, imgW, imgH, expand)` | 由车框算 ROI：按框**自身宽高**的 `expand` 倍外扩，**向外取整**（左/上 `floor`、右/下 `ceil`），再 clamp 到图内 |
| `RoiRect::ContainsBox(box)` | ROI 是否覆盖 **(车框 ∩ 图)** —— 车框可以超出图边界，要盖的是交集 |
| `LprCropRoi(src, roi, out, err)` | 纯逐行 `memcpy`，**无插值、无格式转换** ⇒ 像素与源图逐字节相同 |
| `LprRoiMapRect` / `LprRoiUnmapRect` / `LprRoiMapRects` | ROI 局部坐标 ⇄ 源图坐标 |
| `LprRgbSum(img)` | RGB 之和（跳过 alpha），与 `PlateResult::cropSum` **同口径** |
| `LprRoiSelfTest(img)` | 25 条设备侧单元断言，逐行报告 |

**NAPI**：`roiSelfTestAsync(rgba,w,h)`、`roiPlateProbeAsync(vehId,detId,recId,clsId,rgba,w,h,boxIdx?,expand?)`，均走 `*Async`。
**ArkTS**：探针台加「ROI 自证」「ROI 探针」两个按钮。
**PC 侧判据**：`_veh/roi_selftest_check.py`（几何 + 像素双重复核）、`_veh/roi_probe_check.py`（映射是否偏移）。
**驱动工具**：`_veh/dev.py`（`state`/`layout`/`struct`/`start`/`tap`/`log`/`ps`），用 Python 取回 hdc 输出。

### 关键设计：向外取整

`floor` 左/上、`ceil` 右/下。向内取整会切掉车框边线上的像素，而车牌经常贴着框的边线 ——
这是"少一个像素就丢一块牌"的地方。设备侧用例 `roi-round-outward` 专门钉这一点：
小数框 `(30.4,40.6,130.4,140.6)` 在 15% 外扩下必须是 `15,25,131,131`；
向内取整会给 `15,25,130,130`，断言会红。

### 验收证据

**一、ROI 裁剪与坐标映射（25/25，设备侧断言 + PC 侧独立重算）**

```
[t3check] 整图 rgbSum 设备=66637791 PC=66637791 ✓
[t3check] ✓ crop-interior-bytes  几何: PC 重算一致; rgbSum=25501141 ✓(PC 重算一致)
[t3check] ✓ crop-clamped-bytes   几何: PC 重算一致; rgbSum=21232457 ✓(PC 重算一致)
[t3check] 设备侧 ok=1 的 case: 25 / 25
[t3check] ✓ T3 自证通过：几何与像素两项都由 PC 侧独立重算确认
```

**两重独立**：几何由 Python `math` 重算（与 C++ 是两份实现）；像素由 numpy 从同一张 PNG
重算区域 RGB 和，与设备报的 `rgbSum` 比。**不是同一条代码自说自话。**

**二、ROI 路径 → 车牌检测 → 映射回原图（`_veh/t3_probe.txt`）**

```
[t3probe] boxIdx=0 direct=1 veh=5 roi=(0,47,279,156) coversBox=1 expand=0.1500 roiPlates=1
[t3probe] ✓ boxIdx=0 roiPlate#0 rect=107|114|170|130 score=0.8557 directJ=0 IoU=0.8750 code=浙AG557A
[t3probe]   直检对应 direct#0 rect=107,113,171,131 score=0.870800 code=浙AG557A
```

⇒ ROI 路径映射回来的框与**整图直检**框重合（IoU **0.875**），且两侧读出**同一块牌** `浙AG557A`。
各边最多差 1 px —— 因为 ROI 改变了 letterbox 几何（`r`/`left`/`top` 不同），
检测器的亚像素落点会略移，这是预期的，不是映射错。

### 覆盖缺口（如实记，不粉饰）

**x 方向偏移没有被端到端覆盖。** 本素材里唯一能检出车牌的车框贴着左边缘，
`LprRoiFromBox` 把它 clamp 成 `x0 = 0` —— 这时"忘了加 `x0`"与"映射正确"结果**完全一样**。
`boxIdx=4` 那个框虽然 `roiX0 = 16 > 0`，但它（远处卡车）检不出车牌。

**为什么仍可判定覆盖充分**：端到端只需证明"映射这一步真的被调用了"，而 y 方向
47 px 的偏移已经证明了这一点（IoU 0.875 而非 0）；`LprRoiMapRect` 的 x/y 两个分量
由设备侧单元用例钉死（`map-int` → `85,85,95,95`、`map-float` → `86.5,…`、
`map-vehicleboxes` → `85/90/100`，都带 x 偏移 85）。**残余风险仅为"x 那一行单独写错"**，
而那三条例外已经把 x 那一行锁住了。

### 踩到的坑（都已在代码/脚本注释里留痕）

1. **车辆检测器 ≠ 车牌检测器**。探针第一版把 `s.det`（y5fu_320x 车牌检测器）当车辆模型传给
   `LprVehicleDetect`，设备上报 `yolov5u 期望单输出，实际 3`（那是车牌检测器的 3 个 head）。
   两个模型必须分别持有会话 id（`vehId` vs `detId`）。**这个 bug 是探针自己抓出来的。**
2. **反向用例不能"随便缩一点"**。`cover-negative` 第一版把 ROI 缩 1 px 就断言"覆盖性必须变假"，
   实测 `ok=0` —— ROI 有 15% 外扩余量（每边 15 px），缩 1 px 仍然盖得住。
   缩到 `x0+w < ceil(box x2)` 才构成反例。**断言"必须能失败"这条纪律救了它**：
   否则一个恒真的谓词会安静地通过。
3. **日志与返回串的字段名是两套**。hilog 里是紧凑写法（`roi=x,y,w,h`、`direct=`、`roiPlates=`），
   NAPI 返回串里是 `roiX0`/`directCount`/`roiCount`。PC 判据脚本只认一种就会把字段读成 `None`，
   然后对着一堆 `None` 报"未覆盖"—— 看着像实现有问题，其实是解析问题。
4. **设备 SP 版本串触发发布门禁**。HarmonyOS 版本号后面括号里那段 SP 串（形如
   `6.1.0.135` 之后的服务包标识）并不是序列号，但 `scan_for_publication.py` 按
   "字母数字混合的设备标识"判**阻断**。
   已从 spec 与 GitHub 评论里清掉 —— 去掉不影响可复现性（`MIA-AL00` + `6.1.0.135` + API 24 已足够）。
   **教训两条**：① 往文档里贴设备版本串之前先想一下门禁；
   ② **解释"这个串会触发门禁"时也别把串本身写进去** —— 第一版就是这么写的，
   结果文档自己把门禁又踩了一次。

### 门禁

| 项 | 结果 |
|---|---|
| `_veh/roi_selftest_check.py` | ✓ 设备 25/25 + PC 侧几何/像素独立复核一致 |
| `_veh/roi_probe_check.py` | ✓ IoU 0.875、车牌串逐字符一致 |
| App 构建 / 华为签名 / 装机 | ✓（`SignHap` 仍是已知 CLI 限制） |
| `tools/verify_published_numbers.py` | ✓ 67/67 |
| `tools/scan_for_publication.py` | ✓ 0 阻断（1 项文本待确认：论文联系邮箱） |

## 九·补三、T4 实施记录（2026-09-22）

### 做了什么

| 接口（`lpr_pipeline.{h,cpp}`） | 作用 |
|---|---|
| `PlateResult::ownerVeh` | 车牌归属的车辆框下标（-1 = 无归属）。**界面画「车牌→哪辆车」连线的唯一依据** |
| `RoiPipelineOptions` | `vehConf=0.05`(D1) / `roiExpand=0.15` / `dedupeIou=0.5`(D3)，全部可调 |
| `RoiPipelineStats` | 分段统计（**不补零**：没发生的阶段保持 0） |
| `LprDedupePlates(plates, iouThresh)` | 按 `detScore` 降序贪心去重；保留高分、与输入顺序无关 |
| `LprDedupeSelfTest()` | 10 条纯数据单元断言 |
| `LprRunRoiPipeline(...)` | 端到端：车辆检测 → **逐框** ROI → 逐框车牌检测 → 映射回原图 → 合并去重 |
| `LprOverlapDedupeProbe(...)` | **构造重叠车框**的集成验证 |

NAPI：`roiPipelineAsync(vehId,detId,recId,clsId,rgba,w,h,vehConf?,roiExpand?,dedupeIou?)`、
`roiDedupeSelfTestAsync()`、`roiOverlapSelfTestAsync(vehId,detId,recId,clsId,rgba,w,h)`。

一个实现细节值得记：**单个 ROI 失败不让整帧失败**（计入 `roiSkipped` 继续下一个）。
一帧多车时，一个框裁坏不该把其它车的结果一起丢掉。

### 验收证据

**一、合并去重生效（票面明确要求「构造重叠车框验证」）**

单元用例 10/10（`_veh/devlog_T4DEDUPE.txt`）：完全重合 / IoU 0.667 / IoU 0.333 / 链式重叠 /
顺序无关 / 边界相接 / 空输入 / 单条 / 归属保留 / 输出降序。

但**单元用例喂的是重叠的「车牌框」，不是票面说的「车框」**。所以补了整条因果链的集成验证：

```
T4OVERLAP case=overlap-dedupe;ok=1;growPx=6;boxA=19,65,245,184;boxB=13,59,251,190;
          roi0=0,47,279,156;roi1=0,39,287,171;raw=2;kept=1;iouBefore=0.888889;
          codeBefore=浙AG557A;keptCode=浙AG557A;keptScore=0.855748
```

车框 B 是**人为构造**的（A 向四周各外扩 6 px），与 A 必然重叠；两个重叠 ROI 各自跑车牌检测
⇒ **raw=2**（同一块牌被检出两次，两次的框 IoU 0.889）⇒ **kept=1**（去重收敛），且保留的是
同一块牌 `浙AG557A`。这条是 T4 去重生效的**直接证据**。

**二、ROI 路径端到端可跑（`_veh/t4_check.txt`）**

```
T4PIPE veh=5 truncated=0 roiTried=5 roiSkipped=0 rawHits=1 dropped=0 count=1
        vehInferMs=87.13 roiDetectMs=66.82 totalMs=158.47
T4PLATE idx=0 rect=107,114,170,130 score=0.8557 owner=0 colour=green code=浙AG557A recConf=0.990
```

判据（`_veh/roi_pipeline_check.py`）全过：去重账平（`rawHits - count == dedupeDropped`）、
车框账平（`roiTried + roiSkipped == vehCount`）、每条车牌 `owner ∈ [0,vehCount)`、
颜色只取 blue/green/yellow/unknown（ADR-0005 像素测量口径，**未引入分类器**）、检出即非空串。

⚠️ **如实说明**：这张测试图只有一块车牌，`dropped=0` —— 即**去重在这张图上根本没被触发**。
"去重生效"的证据来自上面的构造用例，不是来自这一行。把 `dropped=0` 说成"去重验证通过"是错的。

**三、CCPD 召回（票面：91.0% ± 1pp，不得低于 90%）**

```
配置 320|0.15：ROI top1=0.905 any=0.907（直检 top1=1.0）；无车辆率=0.085
```

**落在带内**（0.905 / 0.907 均在 0.90–0.92）。与研究笔记 §5.8 的 0.9100 差 0.3pp，
原因是原测量用的车辆权重文件 `_veh/yolov5su.onnx` 已不在工作区，本次用的是
`_veh/yolov5su_320.onnx` —— **这 0.3pp 的差异来源是权重文件版本，不是实现差异**，如实记录。

**口径说明**：这个召回是**主机侧**测量（`_veh/roi_vs_direct.py`），它复用
`hlpr_reference.py` —— 与 native 代码同源的权威后处理实现。设备侧不可能读 CCPD 真值框，
1000 张过设备也不现实。所以：**召回由主机侧测，设备侧负责证明实现与主机一致**
（T2 的逐元素对照 + T3 的几何/像素双重复核）。

### 踩到的坑

1. **日志与返回串字段名两套 —— 第二次踩。** T3 的判据脚本已经因为这个把字段读成 `None`，
   当时也在 spec 里记过；T4 的脚本又踩了一遍（`veh=` vs `vehCount`、`dropped=` vs `dedupeDropped`），
   这次直接 `KeyError` 崩了。**规律：hilog 走紧凑名（省日志长度），返回串走语义名。**
   两个脚本现在都做了归一化 —— 但更该做的是让 native 侧两处用同一套名字。
2. **`rect` 的分隔符也不一致**：hilog 用逗号，返回串用竖线。判据脚本统一成竖线再解析。
3. **解释"某个串会触发门禁"时，别把那个串写进文档。** 第一版在 spec 里引用了设备 SP 版本串
   来说明它会被拦，结果文档自己把门禁又踩了一次。

### 留给 T5 的小问题（已发现，不藏）

- 探针台底部按钮从 4 个涨到 6 个后，最右的「清空」右边缘贴到屏幕边（`x2 = 1224`），
  右侧 12 px 内边距被吃掉。功能无影响，但视觉上是缺陷；T5 重做界面时一并处理。
- 研究笔记 §6 提的「并行双路 + ROI 降级为自动兜底（不做手动开关）」**没有被本 spec 采纳** ——
  spec D2 与 T5 票面选的是「两条路径可切」。两处文档口径不一致，**需要用户拍板**后统一。

### 门禁

| 项 | 结果 |
|---|---|
| `_veh/roi_pipeline_check.py` | ✓ 去重自证 10/10 + 构造重叠车框 raw=2→kept=1 + 账目/归属 + 召回在带内 |
| App 构建 / 华为签名 / 装机 | ✓ |
| `tools/verify_published_numbers.py` | ✓ 67/67 |
| `tools/scan_for_publication.py` | ✓ 0 阻断（1 项文本待确认：论文联系邮箱） |

## 九·补四、T5 实施记录（2026-09-22）

### 做了什么

相机页把车辆流水线的结果**画出来**，并提供 ROI / 直检两条路径的切换：

- **叠加层**（`overlayLayer`）：车辆框描边 + 左上角 `#N` 编号徽标；车牌框用
  **同一个编号、同一个颜色**描边。无归属的车牌框（直检路径 `owner=-1`）用红色。
- **读数卡**：车牌串 + 颜色 + 归属（`颜色 green · 归属 车辆#0`）。
- **分段读数**：ROI 路径下多一行 `veh 73.3 + roi 69.0 ms · 车框 4 · 去重丢 0`；
  直检路径下为空（免得挂着上一路的数）。
- **路径切换**：`全图直检 / ROI 路径` 分段控件。界面显示的是 **native 的回执**
  （`useRoi`），不是界面的意图 —— 开关点了但 native 因缺车辆会话回落直检时，
  界面会如实显示"实际走的还是直检"。

### 关键设计

**用「编号 + 同色」表达归属，不用连线。** 连线的正确性只能靠看图验证（本项目
看不了图）；编号 + 同色是可以程序化核对的：布局树能 dump 到 `#N` 徽标，截图能
按颜色找到描边。

**「喂图自证」入口（`feedTestImage`，长按大标题触发）。** T5 验的是呈现层，而真机上
让相机**碰巧拍到车牌**不可复现（朝向、光照、焦距都不可控）。于是把 `veh320.png`
预编码成 NV21 塞进 rawfile，喂进去走**与相机帧完全相同的入口**
（`cameraFrameAsync`）与**同一段后处理**（`applyFrameResult`）—— 验的是相机页
本身，不是一条旁路副本。

为此把 `infer()` 里「结果串 → 界面状态」那段抽成 `applyFrameResult(raw)`；
帧统计（`record` / `finishFrame`）留在调用方，因为**喂图不是相机帧，不该进
fps / p50 / 丢帧统计**。

**NV21 编码用 native 同源的算术。** `_veh/make_nv21_fixture.py` 的反解直接 import
`tools/verify_nv21_to_rgba.py` 里的 `_yuv`（那是与 C++ 逐位一致的实现）。编码损失
实测：**PSNR 40.3 dB，亮度平均差 0.2、最大 4.97**（色度 2×2 子采样会糊，但车牌
检测主要吃亮度）。在反解图上跑 PC 参考车检，**主车框完全保留**（score 0.9365 vs
0.9355，rect 偏差 < 0.15 px）。

### 踩到的四个坑（都已修）

1. **`v<i>` 字段段数两处不一致 → 车框被静默丢光。** camera 路径给 3 段
   （`classId,score,rect`），T4 探针路径给 4 段（多一个类别名），而界面按 4 段判定
   ⇒ 4 个车框全被 `continue` 掉。症状是 native 报 `vehCount=4` 而界面 `vehDraw=0`，
   **不报任何错**。已统一为 4 段，并把 ArkTS 侧的判定改成按「实际要用的段数」
   （前 3 段）—— 判定要按"这段代码用几段"写，不能按"另一条路径给了几段"写。
2. **`ensureSessions` 早退条件漏掉车辆模型。** 车辆模型是懒加载（只有 ROI 路径要），
   但早退条件只查三个主会话 —— 从直检切到 ROI 时直接返回 true，`veh` 永不加载
   ⇒ `useRoi=true` 而 `vehId=-1` ⇒ native 报 `bad vehicle session id`，而界面只会
   说"喂图失败"。已抽 `loadVehSession`，并给"三个主会话已就绪、只差车辆模型"
   一条单补路径。
3. **`onAreaChange` 给的预览区尺寸会过期。** 预览区高度由 `layoutWeight(1)` 分配、
   随读数卡行数变化，而 `onAreaChange` 只在"变化那一刻"触发。实测抓到 `viewH`
   停在 **315.53 vp** 而实际已是 **341.31 vp**（差 25.8 vp ≈ 74 px）—— `scale`
   因此算小，4 个框**全部系统性偏移**，且表现为「整体缩放」而不是「整体平移」
   （因为 scale 是按错的 viewH 算的），极易被误读成"坐标公式写错"。已改为每次
   重算时用 `getRectangleById(PREVIEW_ID)` 取**实时**几何。
4. **喂图后相机不恢复 → 用户以为 App 卡死。** 停相机是为了稳定取证（否则帧回调
   会在 ~33 ms 内覆盖掉刚写进去的状态），但没给恢复入口。已改为**延迟 10 s 自动
   恢复**，并在状态栏写明"10 s 后自动恢复相机"。

### 验收证据（三条独立判据 + 一条元验证）

| 判据 | 覆盖 | 结果 |
|---|---|---|
| `_veh/camera_ui_check.py`（ROI） | 层1 几何自证 / 层2 布局落地 / 层3 语义 / 层4 计时口径 / 层5 ARGB 约定 | ✓ 五层全过 |
| 同上（直检） | 同上 + `owner=-1`、分段读数为空 | ✓ |
| `_veh/verify_overlay_pixels.py` | 从**截图**里按期望颜色找描边，与期望坐标比对 | ✓ |
| `_veh/selftest_camera_ui_check.py` | **判据脚本自身的元验证**（正确输入放行 + 6 类错误输入全拦） | ✓ |

**层1**（`overlayRect` 是纯函数）：用日志里的 `src/view` 独立重算 `scale/off/draw`，
与设备报的 `draw` 逐框比对 —— 5 个框最大差 **0.0076 px**。

**层2**（布局引擎实际摆放）：布局树 dump 出的 `#N` 徽标坐标 vs 预计算 draw 换算到
屏幕坐标 —— 4 个框偏差 **3.6–4.5 px**，正好是 1.5 vp 边框（≈4.3 px）的内缩量。

**层3**（语义）：ROI 路径 `plate=浙AG557A colour=green owner=0`；直检路径
`owner=-1`、分段读数为空。与 T4 已确立的期望一致。

**层4**（票面硬约束）：相机运行时 `余量 6.3 ms` + 说明含「服务时间，非 fps」；
**喂图后余量变成 `—`** —— 这反过来证明喂图没有污染帧统计。

**层5**（ARGB 约定）：全文件 10 种 hex 颜色**全部是 6 位**（不存在 8 位 hex 被当成
CSS RGBA 的风险），半透明一律走 `rgba()`。

**像素判据**：截图 1224×2776，按 `VEH_COLOURS`（从 ArkTS 源码读出，不硬编码）在期望
边界 ±6 px 内找目标色 —— veh#0 / #2 / #3 与 plate#0 的四条边命中率 **98–100%**，
中位色距 **1–29**，位置偏差 **±3.4 px**（即边框内侧半宽 2.15 px 加 JPEG 抗锯齿）。

> 注：veh#1 的四条边命中率 0%，因为它与 veh#2 的框只差 1 px（模型对同一目标给了
> cls=2 与 cls=3 两个框，class-wise NMS 不互相抑制），绿色描边被后画的蓝色完全
> 覆盖。**这是正确的绘制顺序**，判据已识别并记为"预期被覆盖"而非失败。

### 已知问题（T5 未解决，需单独立项）

1. **ROI 路径耗时 147 ms/帧**（veh 73 ms + roi 69 ms），远超 33.3 ms 帧预算；直检
   路径 59 ms。相机在 ROI 路径下会严重掉帧 —— 用户的体感就是"卡"。
2. ~~**重复车框**：同一目标被 cls=2/cls=3 各出一个框（IoU 0.99），两个 ROI 都跑了
   车牌检测。~~ **已处理（见「九·补五」）**：加了车框层面的跨类别去重。
3. 探针台底部按钮右边缘贴屏（T4 遗留，视觉缺陷）。

### 门禁

| 项 | 结果 |
|---|---|
| App 构建 / 华为签名 / 装机 | ✓ |
| `_veh/camera_ui_check.py`（ROI + 直检） | ✓ 五层全过 |
| `_veh/verify_overlay_pixels.py` | ✓ |
| `_veh/selftest_camera_ui_check.py` | ✓ 元验证（6 类错误全拦） |
| `tools/verify_published_numbers.py` | ✓ 67/67 |
| `tools/scan_for_publication.py` | ✓ 0 阻断（1 项 WARN：论文联系邮箱，属用户决定范围） |

## 九·补五、车框跨类别去重与 top-N 量测（2026-09-22）

起因：用户反馈 ROI 路径"卡"，建议"车辆识别弄个 conf 限制"。**先量测再改。**

### 量测：top-N 的代价（CCPD，conf=0.05 保持 D1）

| top-N | roi_any | 实际跑的车牌检测数/张 |
|---|---|---|
| 1 | 0.9100 | 0.94 |
| 2 | 0.9300 | 1.353 |
| 3 | 0.9300 | 1.533 |
| 5 | 0.9300 | 1.67 |
| 全部 | 0.9300 | 1.743 |

`veh_boxes_per_image_mean = 1.743` —— CCPD 每张图平均不到 2 个车框。
**top-N=2 是零召回代价**（省 22% 车牌检测）；N=1 才掉 2pp。

> ⚠️ 别被 stdout 里那行 `牌宽 300-infpx n=49 ROI 0.775` 误导 —— 那是
> **「牌宽≥300px」子集**的召回。我先据此以为"N=5 也掉 13pp"，实际全体是 0.9300。

### 结论：不调 conf，改成车框跨类别去重

- **调高 conf ≈ top-N 限制**，而 D1 的"低阈值"有实测支撑（召回 82.5% → 91.0%），
  不该动。top-N 更可控（按分数排序）。
- **CCPD 不能用来定 top-N 默认值**：它是单车/车牌特写场景，真实多车场景
  `veh/img` 会大得多。所以 `vehMaxBoxes` 默认 **0（不限）**，只作可调开关。

**实际改动**：`LprDedupeVehicles`（`lpr_pipeline.cpp`）—— 按分数降序、**跨类别**
NMS，`vehDedupeIou = 0.6`。放在**逐框遍历之前**：省的是整次「裁 ROI + 车牌检测」
（每次约 17 ms），而不只是最后那步车牌框去重。这是 **D3 在车框层面的对应物**。

阈值取 0.6 而非 D3 的 0.5：车框比车牌框大，前后两辆车紧挨时车框本身 IoU 就可能
到 0.4~0.5，用 0.5 有把两辆真车合并的风险；而同一目标被标成两个类别实测 IoU 0.99。

### 证据

| 判据 | 结果 |
|---|---|
| `_veh/veh_dedupe_check.py`（PC 侧独立复刻） | ✓ veh320 上 4 → 3，丢掉的与更高分保留框 IoU 0.985，保留框两两最大 IoU 0.0357 |
| 全量 CCPD 去重开/关对照（n=1000） | ✓ 召回 **0.9070 完全不变**；ROI 数 1.722 也不变 |

**如实记录**：去重在 CCPD 上**零触发**（去重前后框数一致）—— 它是"修掉一个真实但
低频的浪费"，**不能指望它解决性能问题**。veh320 上那次 4→3 是个例。

### 耗时分解（真机 ROI 路径 147 ms/帧）

- 车辆检测 **73 ms**（320×320，CPU）—— 去重/top-N **省不了它**
- 车牌检测 **69 ms / 4 框 ≈ 17 ms 每框** —— 去重与 top-N 省的是这里
- 直检路径 59 ms

⇒ 要进 33.3 ms 预算，必须动**车辆检测的落点（上 NPU）**或把多个 ROI
**批量成一次推理**。这两条应单独立项（spec §5 已有前置任务）。

## 九·补六、T6 真机性能实测（2026-09-22）

设备：**`MIA-AL00`（商品名 `nova 14 Pro`）**。票面写的是 `MIA-AL00`，早期笔记写的是
`nova 14 Pro` —— **这两个是同一台机**：`const.product.model = MIA-AL00`、
`const.product.name = nova 14 Pro`。此前以为「票面机型与实际机型不符」，是误判，
不存在需要选设备的问题。（hdc 连接标识已脱敏，不入文档。）
耗时与机型绑定，如实标注以免混用。

### 结论：直检在预算内，ROI 必然超预算

| 路径 | frameMs p50 | 与 33.3 ms 预算 | fps | 丢帧 |
|---|---|---|---|---|
| **直检** | **32.00 ms** | **+1.30 ms** | ~23 | 0 |
| **ROI** | **124.00 ms** | **−90.70 ms（3.7 倍）** | 8~11 | 0 |

各跑 75 s（跨过 45 s 稳态门），取后 1/3 窗口的中位。

### 地板在车辆检测，不在车框数

| 项 | 值 | 来源 |
|---|---|---|
| 车辆检测 | **≈ 73 ms（固定，与车框数无关）** | 界面分段读数 `veh 73.2759` |
| 每框车牌检测 | **≈ 20 ms** | `roi 20.09 ms / 1 框`、`55.57 ms / 3 框` |
| conv（NV21→RGBA） | 2.2 ms | STAGE 行 |
| 其余（NAPI / letterbox / NMS） | ≈ 28 ms | 差值 |

**决定性证据**：STAGE 行 `count=0`（**一个车牌都没检出**）时 `infer=74.61 ms` ——
**什么都不检也要 75 ms**。车辆检测单项就是 33.3 ms 预算的 **2.2 倍**。

⇒ **减少 ROI 数 / 跨类去重 / top-N 都只能削 roi 那段（每框 ~20 ms），救不了 73 ms 的地板。**
唯一有希望的方向是**降低车辆检测本身的开销**（上 NPU 或降输入分辨率），属 T8。

### 原始证据

`_veh/t6_rate_direct.txt`（38 个 RATE 窗口）、`_veh/t6_rate_roi.txt`（37 个）、
`_veh/t6_layout_roi.txt`。判据脚本 `_veh/camera_perf_check.py`（合成日志自测过两条分支：
预算内 32.10 ms / 超预算 153.00 ms 并算出需减 8 个 ROI）。

### 未完成项（如实记录）

**两条路径在同一真实场景下的召回/误检对比未采集。** 需要真实道路/停车场素材（多车、
远距离、干扰），本次采集期间相机没对着这类场景；两次采集场景不同，**混在一起比会得出
假结论**。采集方法已就绪，只缺素材。

### 观察项（不阻塞）

抓布局树时 `roiSegText` 偶发为空（`实际：ROI` 在、`车框 …` 那行不在）。界面写的是
`Text(roiSegText.length > 0 ? roiSegText : ' ')` —— 纯空白 Text 在 dump 里可能被跳过；
也可能确有一帧未写。待查。

## 九·补七、T8 换原版 YOLOv5 与 NPU 转换（2026-09-22）

动机接「九·补六」：ROI 路径的**下限是车辆检测 73 ms**，占满 33.3 ms 预算的两倍多。
要压下去只有一条路 —— 把车辆检测从 CPU/ncnn 挪到 NPU。而当前车辆模型
`yolov5su_320_veh_fp32.ms` 是 ultralytics 的 **v5-u（含 DFL）**，**DFL 那个 rank-4 permute
过不了麒麟 NPU 的 Transpose 硬门**。所以必须换回**原版 anchor-based YOLOv5**。

### 三条硬门结论（均为扫描器原话，不是推测）

| 模型 | 判词 | 结论 |
|---|---|---|
| v5-u 裸导出 | `/model.24/dfl/Transpose perm=[0,3,1,2]` | 不过 |
| 原版 v7 裸导出 | `/model.24/Transpose perm=[0,1,3,4,2]`（**rank-5**） | 不过 |
| 原版 v7 **裁掉解码段** | `✓ 硬门1 过：所有张量 rank ≤ 4` + `Transpose 共 0 个` | **两条全过** |

**关键认识**：原版 v7 的失败点不在 DFL，而在 Detect 头把
`view(bs,na,no,ny,nx) → permute(0,1,3,4,2)` **连同 sigmoid 与 anchor-grid 解码一起放在
rank-5 上跑**。所以**不能只删 Transpose** —— 要按 `kirin-npu-model-porting` 第二节
「切在最后一个 rank-4 张量」，把整段解码搬出计算图。

### 切点定位与数值自证

沿 `/model.24/Transpose*` 反查 producer，得 `Transpose ← Reshape ← Conv`，
故 rank-4 边界即 `/model.24/m.{0,1,2}/Conv_output_0`。反向可达裁切后：
节点 292 → 231（删 61 个解码节点），常量 120 → 120（**丢 0** —— rank-5 常量随之消失），
输出 `(1,255,40,40) / (1,255,20,20) / (1,255,10,10)`。

**裁切是否改变语义**，用「原图跑 ORT 取 output0 ↔ 裁切图跑 ORT + numpy 复现解码」逐元素比：

    maxAbsDiff = 9.155273e-05    meanAbsDiff = 9.736768e-08
    maxAbsDiff / mean|ref| = 1.922e-05

属 float32 累积噪声量级。**解码常量从原图里抽出来**（不手抄），抽出的值与 YOLOv5 官方规格
逐字一致：anchors `[[10,13],[16,30],[33,23]] / [[30,61],[62,45],[59,119]] / [[116,90],[156,198],[373,326]]`，
strides `[8,16,32]` —— 这也是「权重确为原版」的旁证。

### converter 结果对比（同一台机器，MindSpore Lite 2.6.0）

| ONNX | converter 结果 |
|---|---|
| v5-u（含 DFL） | **失败**：`InferShapeByNNACL for op: /model.22/dfl/conv/Conv failed` → `Convert failed` |
| 原版 v7 裁切后 fp32 | `CONVERT RESULT SUCCESS:0`，日志**零告警**（28.95 MB） |
| 原版 v7 裁切后 fp16 | `CONVERT RESULT SUCCESS:0`，日志**零告警**（14.50 MB） |

### 权重来源与可复核凭据

- sha256 `8b3b748c1e592ddd8868022e8732fde20025197328490623cc16c6f24d0782ee`，14,808,437 B
- 加载后自证：`213 layers, 7225885 parameters, 16.4 GFLOPs`；anchor 3 层、**无 DFL**；前向 `(1,6300,85)`
- 导出用 **yolov5 v7.0 源码**（`git clone --depth 1 --branch v7.0`），不用 PyPI 轮子
- 许可：yolov5 仓库是 **GPL-3.0**（与 ultralytics 8.x 的 **AGPL-3.0** 不同，README 已分开列）

### 踩到的 5 个坑（已写进脚本注释，避免重踩）

1. **ultralytics 8.4 静默换权重**：传 `yolov5s.pt` 实际加载 `yolov5su.pt`，产物仍命名
   `yolov5s_320.onnx` —— 名字对、内容错。→ **一律以 `scan_onnx.py` 结果为准，不看文件名**。
2. **PyPI `yolov5==7.0.14` 不可用（两处）**：`from huggingface_hub.utils._errors import …`
   （本机 hf_hub 1.24 已删该模块）；且 `attempt_load` 内是裸 `from models.yolo import …`
   （轮子把 `models/` 放在包**内**）。→ 必须用 v7.0 **源码仓库**，仓库根进 `sys.path[0]`。
3. **setuptools ≥ 81 不再发布 `pkg_resources`**，而 yolov5 仍 `import pkg_resources as pkg`。
   → 不降级全局 setuptools（83.0.0 已被其他工具链占用），改 `--target _veh/pylibs --no-deps`
   装旧版并在脚本内临时追加 `sys.path`。
4. **torch ≥ 2.6 把 `torch.load` 的 `weights_only` 默认改成 True** → 权重里的
   `models.yolo.Model` 不在白名单。→ 仅在导出进程内改回 `False`，并打印 sha256 作为可信凭据。
5. **torch 2.13 的 `torch.onnx.export` 默认 `dynamo=True`**（依赖 `onnxscript`）。
   → 显式 `dynamo=False` 走 yolov5 原本的旧版 TorchScript exporter，不引入未经验证的新导出器。

### 真机验证（T8 第 3、4 项）

设备 **`MIA-AL00`（商品名 `nova 14 Pro`）**，API 24。模型进 rawfile 后走
`probeAll` / `detDriftProbe`（后者每行带 `mk=<模型>` 以区分多模型）。
判据只认 `landed=` 这个**实际落点**字段 —— 请求后端与落点是两件事。

| 模型 | 后端 | `landed`（实际落点） | p50 (ms) | mean (ms) |
|---|---|---|---|---|
| `y5fu_320x_head_fp32.ms`（对照：车牌侧现存裸头） | nnrt | `NNRT:NPU_ohos.boot.hardware.kirin8020_v2_0` | 5.054 | 4.743 |
| 同上 | cpu | `CPU` | 8.178 | 8.290 |
| **`yolov5s_v7_320_npu_fp32.ms`** | nnrt | `NNRT:NPU_ohos.boot.hardware.kirin8020_v2_0` | **5.392** | 5.395 |
| 同上 | cpu | `CPU` | **42.016** | 41.109 |
| **`yolov5s_v7_320_npu_fp16.ms`** | nnrt | `NNRT:NPU_ohos.boot.hardware.kirin8020_v2_0` | **5.537** | 5.514 |
| 同上 | cpu | `CPU` | 41.646 | 40.559 |

**落点是真的 NPU，不是静默回落** —— 两条自证：

1. `landed` 逐字回 `NNRT:NPU_ohos.boot.hardware.kirin8020_v2_0`（含设备名）。
2. 同一模型 nnrt 与 cpu 的 checksum **不同**（fp32：`L2=3491.7710` vs `3492.3102`，
   `maxAbs=17.4844` vs `17.5216`）。若 nnrt 静默回落 CPU，两者必须**逐位相同**。

**同引擎同模型的后端比**（MS Lite 内部 —— 这是唯一能隔离出 NPU 收益的口径）：

| 模型 | NPU p50 | CPU p50 | 加速比 |
|---|---|---|---|
| `yolov5s_v7_320_npu_fp32.ms` | 5.392 | 42.016 | **7.79×** |
| `yolov5s_v7_320_npu_fp16.ms` | 5.537 | 41.646 | **7.52×** |
| `y5fu_320x_head_fp32.ms`（对照） | 5.054 | 8.178 | 1.62× |

另有**跨框架对照**（T8 组里 ncnn 自证探针同轮产出）：同一份 `y5fu_320x_head` 裸头，
ncnn（Vulkan 生效，`vulkan=1 gpu=ok=1`）p50 = **34.54 ms**，MS Lite NPU = **5.05 ms**，
差 **6.83×**。即「上 NPU」的收益不只来自 CPU→NPU，也来自 ncnn→MS Lite。
同轮 `gpuProbe` 也再次确认 GPU 档不可用：`req=gpu` → `LANDED=CPU fallback=GPU:fp16`。

### 与 T6 的下限对照 —— 口径必须写清楚

T6 测到的车辆检测下限是 **73 ms**（in-pipeline，含 letterbox 预处理 + 解码 + NMS，
CPU/ncnn）；本轮 NPU 裸头是 **5.39 ms**（纯推理，不含预处理与解码）。
**两者不是同一口径，不能相除当加速比。** 可以说的是：

- 裸头同口径下，NPU 比同引擎 CPU 快 **7.79×**；
- 73 ms 里预处理 + 解码 + NMS 占了不少（同轮 CPU 裸头 42.02 ms），
  这部分**不会被 NPU 加速** —— 接入后要看的是端到端 frameMs，不是裸头。

结论：**NPU 是 ROI 路径唯一有量级收益的方向**（T6 已排除去重/top-N 能解决）。
接入属后续 ticket，且须先有 spec —— 裸头只吐 `(1,255,H,W)`，sigmoid 与 anchor 解码
搬到 Host 侧实现是本 ticket 之外的活。

### 一个未解释的观察（不写成结论）

fp16 与 fp32 两份模型在 **nnrt 档**的 checksum **完全相同**（`L2=3491.7710`、
`maxAbs=17.4844`），但在 **cpu 档**不同（`3491.8379` vs `3492.3102`）。
一个可能解释是 NPU 内部按 fp16 执行、两份模型落到同一套 fp16 kernel，
但这只是猜测，**没有证据**，留作观察项。

证据文件：`_veh/devlog_T8V7.txt`（27 行，含 6 条 `DET DRIFT`、3 条 `MATRIX … gpu`、
1 条 `NCNN RUN` 与 Vulkan verdict）。全量原始日志 `_veh/devlog_T8V7_raw.txt`。

## 十、下一步

用户确认本 spec → `to-tickets` 细化 T1–T8 → implement。

**按项目纪律：先 spec 再实现，不写 roadmap 取代 spec。**
