# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root — the glossary. This project has a **single context**; there is no `CONTEXT-MAP.md`.
- **`docs/adr/`** — read ADRs that touch the area you're about to work in. Nine exist at project start (0001–0009); they are the authoritative record of every decision and every **failed route**.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront.

## Layout: single-context

```
/
├── CONTEXT.md          ← glossary (terms only, no implementation detail)
├── docs/
│   ├── adr/            ← 0001-… , sequential, one decision each
│   └── agents/         ← this file, issue-tracker.md, triage-labels.md
└── (app source to be created)
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

**The terms most likely to be got wrong here** — these carry a history of being conflated:

| Use | Never use | Why |
|---|---|---|
| **落点 (LANDED)** | 后端, 委托目标 | Landing is *observed*, not requested. `req=` is the request; `LANDED=` is the fact. |
| **参照串 (reference string)** | 真值, ground truth | A reference string is the reference implementation's own output. Using it as truth is circular — this project was burned by exactly that (ADR-0015 in `lpr-showcase`). |
| **真值 (ground truth)** | 标签, 参照 | Only `_dataset/real/crops/` filenames are ground truth. |
| **服务时间** | fps, 帧率, 吞吐 | `1000/p50(frameMs)` is a theoretical reciprocal, **not** throughput. Only 到达率 / 完成率 may be called fps. |
| **独立委托 vs 融合携带** | 算子支持 | An op rejected standalone may still run on NPU as a Conv's fusion neighbour. |
| **省份偏斜** | 类别不平衡 | The specific failure: the eval set is 956/1000 皖, so province-slot accuracy was never measured. |

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0003 (NPU 利用率不可测), but worth reopening because…_

**Two ADRs in this repo contain corrections of earlier conclusions** (ADR-0005, ADR-0008). When you find a claim that looks wrong, read the ADR's 「更正记录」 section before assuming it's an oversight — the correction may already be recorded.

## Numbers discipline

This repo has a hard rule inherited from both prior projects:

> **数字只在证据落地后才写进论文/简历/网页；三者必须一致。**

- Every performance or accuracy number must trace to a file in `_evidence/` (or the `ShusenPaper` archive).
- Cite the **热态 (thermal level)** and **轮次** alongside any NPU/CPU ratio. CPU-side run-to-run variance was measured at 30–50%; NPU-side under 8%.
- **Never** quote NPU utilisation — it is not readable on HarmonyOS (ADR-0003).
- **Never** quote a cross-stack ratio as if it were like-for-like: NPU runs MindSpore Lite + NNRT, GPU only ncnn-Vulkan. Only same-stack ratios are comparable.
