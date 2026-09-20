# ADR-0001 · 新工程继承前期数据，但不延续其代码库

- **状态**：已接受
- **日期**：2026-09-20
- **前置**：无（本工程起点）
- **后续**：ADR-0002（论文主张）、ADR-0007（范围收口）
- **证据**：`ShusenPaper/`（30 个 git 提交，无 remote）、`lpr-showcase/`（无 git，代码丢失）

## 问题

磁盘上存在两个既有工程：

| 工程 | 性质 | 状态 |
|---|---|---|
| `Desktop\ShusenPaper` | 项目一：麒麟 NPU 系统性表征 | git 30 提交；RQ1 完成；RQ2/RQ3/RQ4 未完成；**无 remote** |
| `Desktop\Test\lpr-showcase` | 项目二：HyperLPR3 端侧车牌识别的**文档与证据层** | **无 git**；模型、证据、论文稿、1000 张真值集尚存 |
| `C:\Users\26671\lpr-harmony` | 项目二：**App 源码与工具链层** | 1.7 GB / 13630 文件；**无 git**；完整可编译（见 ADR-0008） |

新工程与它们是什么关系？

> ⚠️ 本条初版误称 App 源码已丢失。**实际全在 `C:\Users\26671\lpr-harmony\`**——初版搜索只覆盖 `Desktop` / `D:\` / `Downloads`，漏了用户主目录。详见 ADR-0008 的更正记录。

## 决策

**新建独立工程于 `Desktop\车牌识别`，继承两者的数据与结论，但不延续其代码库。**

继承清单：

| 来源 | 继承内容 |
|---|---|
| `ShusenPaper` | L1 算子支持矩阵（36 算子三信号）、L2 加速比套件（5 轮 × 21 模型）、Roofline、INT8 形态结论、三缺陷证据链、华为工单往返 |
| `lpr-showcase` | 三个 ONNX 模型（识别/检测/分类）、77 项字符表、1000 张真值集、30+ 份原始日志、ADR-001~015、IEEE 论文稿、纯前端 WASM 演示代码 |
| 两者 | 设备实测口径（warm-up 10 + 100 次取 P50、≥5 轮、Fisher-Yates 洗牌、checksum 校验、热态标注） |

不继承：两个工程的代码库结构。App 端全部重写。

## 理由

1. **数据不可重建**。`ShusenPaper` 的 5 轮协议数据绑定在门店演示机与华为工单回复上——**机器和回复都不会再来一次**。`lpr-showcase` 的真机 30× p50 矩阵、CANN/NNRT/Vulkan 三路探针同理。
2. **代码库面向不同目标，但并非不可用**。`ShusenPaper/app` 是"表征台"（`runInference` 单函数、50 个算子 `.ms`），产品构建节奏与它不同；`lpr-harmony/LprDemo` 是完整的四段流水线 App（`lpr_pipeline.cpp` 1084 行 + `ms_engine.cpp` 650 行 + `napi_init.cpp` 1082 行 + ArkTS 2400 行），**可编译**。
3. **重写是用户明确要求，不是被迫**。基线是 `lpr-harmony` 这份真实源码，而非备份：`_archive\2026-09-18\old-backups\` 的 09-17 快照缺 `ms_engine.h`/`vulkan_probe.h`，**无法编译**，只作历史参考。

## 后果

- 新论文**必须显式声明**哪些数据来自前期工作，不得与新增数据重复计数。
- `ShusenPaper` 冻结为只读档案，不再提交。
- `lpr-harmony` 作为**重写的参考基线**：它的 `README.md` 记录了构建的全部坑（hvigor 环境变量、`DEVECO_SDK_HOME` 扫描器陷阱、`unset NODE_OPTIONS` 与 safe-delete 冲突、签名 bundleName 约束），`AGENT.md` 记录了工程约定。**这些经验直接继承，不必重新踩。**
- ⚠️ `lpr_pipeline.cpp.yolov8_backup` 与 `lpr_pipeline_new_v2.cpp` 是 A18 §5 记录的**遗留物**（手工合并从未完成）；改端侧代码前先 `assembleHap` 干跑一次编译。

## 边界声明

- 本 ADR **不**主张 `lpr-showcase` 的结论全部有效：其颜色分类器已被独立测量证伪（见 ADR-0005），其"NPU 会翻字符"的归因已被 `ShusenPaper` 的"融合携带"模型重新解释（见 ADR-0002）。
- 本 ADR **不**主张 `ShusenPaper` 的数据可直接复用而不复核：其 checksum 校验发现过两处 FAIL（`native_decode_tail`、`yolov8n` 原版），复用前须确认所用子集已通过校验。

## 未完成动作

1. 为 `ShusenPaper` 与 `lpr-showcase` 建立远程备份（前者 30 提交 + 75 MB 工单包无 remote；后者无 git）。
2. 清点继承清单中每一项的可读性，产出 `docs/inherited-assets.md`。
