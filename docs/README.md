# 文档导览

> 按「读者动线」组织：**你想干什么 → 去哪读**。
> 所有实验笔记与 ADR 均为过程留痕，**不删不改写历史**；已被推翻的结论在原处保留，
> 由后续笔记/ADR 指回（这是本项目的证据纪律，见 ADR-0003）。

## 我想知道这个项目做了什么、结论是什么

1. 根目录 [`README.md`](../README.md)（[中文](../README.zh-CN.md)）—— TL;DR + 三大结论。
2. [`paper/en/main.tex`](../paper/en/main.tex) —— 8 页英文论文稿（IEEEtran）。
3. [`evidence-index.md`](evidence-index.md) —— **每个对外数字 ↔ 证据文件**的对照表，
   由 `lpr-kirin8020-app/tools/verify_published_numbers.py` 机检（91 项）。

## 我想在自己的麒麟设备上复现 / 调用 NPU

1. [`guides/npu-pitfalls-build-and-env.md`](guides/npu-pitfalls-build-and-env.md) —— 构建与环境坑。
2. [`guides/npu-pitfalls-runtime-and-landing.md`](guides/npu-pitfalls-runtime-and-landing.md) —— 运行时与落点坑。
3. [`notes/toolchain-and-sources-on-disk.md`](notes/toolchain-and-sources-on-disk.md) —— 模型/DDK 重建步骤。

## 我想查某个结论的原始证据

- [`evidence-index.md`](evidence-index.md) 是入口；实验笔记在 [`notes/`](notes/)：

| 笔记 | 主题 |
|---|---|
| `t3` / `t6`–`t14` | 实验阶段 T 系列（相机、均衡集、热特性、后端 A/B、配对检验……） |
| `t14-rq4-two-runs` | RQ4 拆两次独立运行（含置换检验：+26.9% 漂移落在噪声分布内） |
| `t8-operator-collision` | 算子覆盖对撞：NNRT 16/36 拒 vs CANN 51/51 过 |
| `vehicle-detection-pipeline-research` | 车辆检测流水线（T5–T8）调研 |

## 我想查「为什么这么做」

- [`adr/`](adr/) 0001–0009 —— 全部架构决策，含被推翻后更正的记录。
- [`../CONTEXT.md`](../CONTEXT.md) —— 单一上下文词汇表。

## 调研报告（research 阶段产物，附来源与可信度标注）

在 [`notes/`](notes/)：`gpu-official-verdict`（GPU 官方结论）、
`harmonyos-npu-gpu-squeeze-research`（NPU/CPU/GPU 通路）、
`on-device-chinese-lpr-survey`（端侧中文车牌识别综述）、
`on-device-decision-model-survey`（端侧决策模型/Jev 可行性）、
`kirin8020-npu-llm-verdict`（端侧 LLM 证伪）、
`ddk-access-and-province-balanced-plate-datasets`（DDK 获取与数据集）。

## 过程记录（归档，反映当时状态）

| 文件 | 状态 |
|---|---|
| [`spec.md`](spec.md) | **实验阶段** spec，实验已全部完成（T1–T14） |
| [`spec-portfolio.md`](spec-portfolio.md) | **交付阶段** spec（本轮收尾依据） |
| [`spec-vehicle-pipeline.md`](spec-vehicle-pipeline.md) | 车辆流水线 spec，T5–T8 已实施 |
| [`paper-and-showcase-plan.md`](paper-and-showcase-plan.md) | 2026-09-21 规划快照，§8.1 已执行完毕 |
| [`grilling-2026-09-22.md`](grilling-2026-09-22.md) | 访谈记录 |
| [`tickets-2026-09-22.md`](tickets-2026-09-22.md) | 工单索引（以 GitHub issues 实际状态为准） |
| [`resume-bullets.md`](resume-bullets.md) | 简历条目素材（与守卫数字同源） |
