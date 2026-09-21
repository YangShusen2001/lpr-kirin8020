# 麒麟 8020 端侧异构推理与车牌识别流水线

> 单一上下文（single-context）。词汇表见 `CONTEXT.md`，决策见 `docs/adr/`。

## 反退化约束（agent 行为，每次会话都适用）

2026-09-21 实际发生过一次：思考块里连续复读数百行 `Let me write. / Writing. / Output.`，
一个工具调用都没发出。机理是**决定之后先写了一句"预备叙述"**——它看起来像进展，
但不产生任何动作，于是每个填充 token 在局部都像"下一步"，没有终止条件。

- **决定之后直接发工具调用，中间不放任何东西。** 不写 `Let me…` / `现在我来…` 这类预备叙述。
- 同一段推理里出现**两次**预备叙述仍未发出调用 → 立即停止，改为动手或提问。
- 计划落 `todo_write` 或笔记文件，**不在思考里反复重述进度**——重述是卡死的高发位置。
- 独立调用**合并**发出：步骤越少越大，预备叙述的机会越少。
- 长自主运行**切段**，段边界落盘，这样卡住时损失有界且可见。

## Agent skills

### Issue tracker

Issues and specs live as GitHub issues on `YangShusen2001/lpr-kirin8020` (private), driven by the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical roles, label string equal to role name: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` glossary plus `docs/adr/` at the repo root. See `docs/agents/domain.md`.

---

## 这个项目是什么

**麒麟 8020 端侧异构推理的落点自证方法学 + 算子覆盖边界**，以中文车牌识别四级流水线（检测 → 透视矫正 → 识别 → 判色）作为应用级案例（RQ3），并测持续负载热特性（RQ4）。

论文主张与范围见 [ADR-0002](docs/adr/0002-thesis-landing-evidence-and-operator-coverage.md) 与 [ADR-0007](docs/adr/0007-scope-rq3-rq4-only.md)。

## 设备与栈

| 项 | 值 |
|---|---|
| 设备 | HUAWEI nova 14 Pro（MIA-AL00）· 麒麟 8020 · HarmonyOS 6.1.0.135 · API 24 |
| 推理 | MindSpore Lite Kit 2.6.0 NDK → NNRT → NPU（`NPU_ohos.boot.hardware.kirin8020_v2_0`） |
| GPU | Maleoon 920C，Vulkan 1.3.275（ncnn-Vulkan 唯一通路） |
| 判色 | 像素测量（**不用**分类模型，见 ADR-0005） |

## 前置资产（不在本仓库内）

本工程继承两个前期工程的数据与结论，**代码库不延续**（ADR-0001）：

| 位置 | 内容 |
|---|---|
| `~/Desktop/ShusenPaper` → [shusen-npu-characterization](https://github.com/YangShusen2001/shusen-npu-characterization) | L1 算子矩阵（36 算子）、L2 套件（5 轮 × 21 模型）、Roofline、INT8 形态结论、三缺陷提单链 |
| `~/Desktop/Test/lpr-showcase` | 三个 ONNX 模型、77 项字符表、1000 张真值集、30+ 份原始日志、ADR-001~015、IEEE 论文稿 |
| `~/lpr-harmony` → [lpr-harmony](https://github.com/YangShusen2001/lpr-harmony) | App 源码（`lpr_pipeline.cpp` 1084 行等）、CANN 转换脚本、`.ms`/`.om` 产物 |

⚠️ **模型与 DDK 不在本仓库**（`.gitignore` 排除）：DDK 匿名可下，`.ms`/`.om` 由 ONNX 经文档化工具链重新产出。重建步骤见 [docs/notes/toolchain-and-sources-on-disk.md](docs/notes/toolchain-and-sources-on-disk.md)。

## 硬约束（写代码前必读）

1. **NPU 利用率不可测** —— 依据是官方文档与工具清单（**未对设备做过逆向尝试**，见 ADR-0003 边界声明）。禁止任何利用率数字。证据只能是延迟差 + 逐算子落点 + 张量指纹（ADR-0003）。若有人通过 profiler 私有接口或内核态拿到 NPU 计数器，本条应被推翻并新建 ADR。
2. **会话必须常驻** —— NNRT delegate 析构路径存在 cppcrash，不可反复创建/销毁。
3. **动态 batch 会导致构图失败** —— 转换时固定 batch = 1。
4. **改端侧代码前先 `assembleHap` 干跑编译** —— `lpr_pipeline.cpp.yolov8_backup` 与 `lpr_pipeline_new_v2.cpp` 是遗留物，手工合并从未完成（A18 §5）。
5. **OMG 输出路径不能含非 ASCII 字符** —— 与 hvigor 拒绝非 ASCII 工程路径（`00306003`）同类缺陷。
6. **持续后台计算不被允许** —— `SystemLoadLevel` 有 8 档，官方要求 HIGH(3) 起停止无感服务。手机侧无通用计算长时任务类型（[notes/unattended-automation-on-device](docs/notes/unattended-automation-on-device.md)；**该结论未在 nova 14 Pro 真机验证**，见其边界）。
