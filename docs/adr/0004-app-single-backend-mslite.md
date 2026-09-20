# ADR-0004 · App 单后端（MindSpore Lite）；双后端对撞只进论文

- **状态**：已接受
- **日期**：2026-09-20
- **前置**：ADR-0002（论文主张）、ADR-0003（证据标准）
- **证据**：`lpr-showcase/_evidence/A17` §4；`docs/adr/ADR-012`、`ADR-013`（lpr-showcase）

## 问题

NPU 有两条通路：MindSpore Lite + NNRT delegate（高层）与 CANN Kit + `.om` 离线模型（直连达芬奇）。App 该支持几条？

## 决策

**App 只做 MindSpore Lite 单后端；CANN 对撞作为论文里的转换脚本 + 对照表存在，不进 App。**

实测依据（`lpr-showcase` A17，同一设备）：

| 模型 | CANN `.om` | MS Lite→NNRT | 谁快 |
|---|---|---|---|
| 检测裸 head | 3.90–5.10 ms | **5.35 ms**（30× p50） | 接近 |
| 识别 rpv3 | 5.19–5.63 ms | **3.99 ms**（30× p50） | **MS 更快** |
| 分类 | 0.95–0.97 ms | 1.00 ms | 接近 |

且 `lpr-showcase` A10 已证明**现有 NPU 通路就是官方 NNRt 底座**：NNRt 枚举出的设备名 `NPU_ohos.boot.hardware.kirin8020_v2_0` 与 MS Lite 落点日志中的设备名**逐字相同**。直连能省掉的最多是一层胶水。

## 理由

1. **对撞表的学术价值与工程成本完全解耦**。转换是一次性脚本（`converter_lite.exe` + OMG），跑完就有数据；App 里维护两套推理引擎的代价是持续的。
2. **选出来还是 MS Lite**。三个模型里 MS Lite 在两个上更快或持平，第三个（分类）已被废弃（见 ADR-0005）。
3. **降低 v1 风险**。v1 目标是"一两周出可演示版本"，双引擎会让冷启动、会话管理、内存占用都翻倍。

## 后果

- App 的推理层只需实现 `MsSession` 一族接口（加载、运行、落点记录、性能模式）。
- 论文保留双后端对撞表，但必须标注**口径不同**：CANN 侧是 3 次原始采样，MS Lite 侧是 30× p50——**只作量级参考**。
- `.ms` 转换链（`converter_lite.exe` 2.6.0，PC 端，**无需华为账号**）是 App 的构建依赖，须写进构建文档。

## 边界声明

- 本 ADR **不**主张 CANN 通路无价值：它已在同一设备上端到端跑通（`compat=0/build_rc=0/run_rc=0`），且其算子清单（166 IR 算子）是 ADR-0002 的"算子覆盖边界"的**另一半对照面**。
- 本 ADR **不**主张 MS Lite 的 GPU 档可用：其 `gpu`/`kirin` 档在编译期即判否（这份 `libmindspore_lite.so` 未编 GPU delegate），全部静默回落 CPU。

## 未完成动作

1. 用 `ShusenPaper/app` 的算子表征台构造 `.om` 版本，与 `.ms` 版本逐算子对撞——**前置是拿到含 OMG 的 DDK（见 ADR-0008）**。
2. 若 DDK 不可得，退化为**文档级对撞**：MS Lite 官方算子表（58/198 有 Kirin NPU 实现，且**全部 FP16-only**）vs CANN 官方 166 IR 算子清单。
