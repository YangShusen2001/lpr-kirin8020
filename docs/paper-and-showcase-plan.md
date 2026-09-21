# 论文与对外呈现规划

> 本文回答六个问题：项目做到什么程度、论文怎么写、语言怎么选、格式要不要 IEEE、
> GitHub 怎么开源、网页与简历怎么写。
> 依据：`docs/adr/0001`–`0007`、`docs/spec.md`、`docs/notes/t3`–`t14` 与两个远程仓库的实际状态。
> 生成日期：2026-09-21。

---

## 0. 一句话结论

**实验主体已经跑完并收口（T1–T14），论文正文一个字都还没写（旧稿已归档），
开源与对外呈现约完成 40%。** 当前最短路径不是"再补实验"，而是
**把已有的 14 篇实验笔记收成一篇论文 + 一个能对外看的仓库**。

三件事按此顺序做：**先定数字口径 → 再写论文 → 最后开源/网页/简历同时发布**。

---

## 1. 项目现状审查

### 1.1 资产盘点（实际在磁盘上的四个工程）

| 工程 | 路径 / 远程 | 角色 | git 状态 |
|---|---|---|---|
| 决策与文档层 | `Desktop\车牌识别` → [lpr-kirin8020](https://github.com/YangShusen2001/lpr-kirin8020) | CONTEXT / ADR / spec / 19 篇笔记 | ✅ 已推送，**private**，37 提交 |
| App 层 | `<REPO>/lpr-kirin8020-app` → [lpr-kirin8020-app](https://github.com/YangShusen2001/lpr-kirin8020-app) | LprDemo 源码 + tools + evidence | ✅ 已推送，**private**，3202 文件 |
| 前期表征 | `Desktop\ShusenPaper` → [shusen-npu-characterization](https://github.com/YangShusen2001/shusen-npu-characterization) | RQ1 数据、L1 算子矩阵、L2 套件 | ✅ **private**，30 提交 |
| 前期 App 源码 | `<PRIOR_WORK>/lpr-harmony` → [lpr-harmony](https://github.com/YangShusen2001/lpr-harmony) | 重写参考基线（1084 行 `lpr_pipeline.cpp`） | ✅ **private** |
| ⚠️ 证据与论文层 | `Desktop\Test\lpr-showcase` | 三个 ONNX、1000 张真值集、30+ 原始日志、**旧 IEEE 论文稿（中英两版）** | ❌ **无 git，未备份** |

> **这是当前最大的单点风险**：`lpr-showcase` 是唯一没有被版本控制覆盖的资产，
> 而它恰好装着真值集、原始日志和旧论文稿。ADR-0001 的「未完成动作 1」早就点了这一条，
> 至今没做。**在写论文之前必须先给它建 git 并推私库**——论文要反复引用里面的证据文件。

### 1.2 实验完成度

| 编号 | 主题 | 状态 | 关键结论 |
|---|---|---|---|
| T1–T5 | App 骨架 / 数据集 / 相机路 / 构建模式 | ✅ | `-O0` 静默覆盖 `-O3`，延迟差 1.7–4× |
| T6 | 省份均衡评测集（26 省，n=3368） | ✅ | **原假设被证伪**：皖偏 90.6% vs 均衡 90.9%，偏斜不抬高准确率，**只决定错误落在哪一位** |
| T7 | RQ4 持续负载热特性 | 🟡 | 25 轮 / 6 分钟，`thermal` 恒 1，**未触发 thermal≥3**；顺带定位并修掉一个输入张量污染缺陷 |
| T8 | 算子覆盖对撞（`.om` vs `.ms`） | ✅ | CANN 侧 **51/51 全通过**，NNRT 侧部分被拒 → **支持性是 模型×工具链 的联合属性** |
| T9 | 60fps 供给下的流水线产能 | ✅ | 相机能给 ~50 fps，流水线吃不下，被**背压**回 36 / 44 fps |
| T10 | 裁剪图工况 det/rec 落点 A/B | ⚠️ 部分被推翻 | 6.8% vs 0.3% —— **裁剪图工况产物**，被 T12 推翻 |
| T11 | 识别器裸测准确率 | ⚠️ 部分被推翻 | 端侧 NPU 89.9% vs 主机 90.6% —— "保真"结论被 T14 推翻 |
| T12 | 真实整车场景 det/rec A/B（n=1000） | ✅ | **det 0.1% / rec 0%**，全流水线 99.1% |
| T13 | 8 字符新能源牌（n=1000） | ✅ | **92.5% vs 99.1%（−6.6 pp）**，逐省对照排除省份构成 |
| T14 | 配对 McNemar | ✅ | **移植不是"保真"**：0:7，p=0.0156；**后端本身是准确率变量**：NPU vs CPU +3.2 pp，p<0.0001 |
| 相机路 | NPU 余量 / 帧率上限 / C8 定位 | ✅ | 检测段占帧预算 **49%**，识别段 **10%**；C8 = DVFS + 线程池唤醒 |

**"做到什么程度"的量化判断：**

| 维度 | 完成度 | 判断依据 |
|---|---|---|
| RQ3（流水线异构放置） | **~90%** | T10–T14 四轮 n=1000 对照已闭环 |
| RQ4（持续负载热特性） | **~50%** | 只跑到 thermal=1、6 分钟；**核心问题"持续负载下 NPU 收益能否维持"尚未回答** |
| 算子覆盖边界 | **~85%** | 51/51 实测 + 166 IR 文档对照；**"融合携带"仍是相关性，未升级为因果** |
| 论文正文 | **0%** | 旧稿（移植保真主张）已按 ADR-0002 归档 |
| 开源交付 | **~40%** | 两个仓库已建但 private；`lpr-showcase` 无 git |
| 对外呈现（网页/简历） | **0%** | spec 的 user story 53–55 全部未做 |

### 1.3 缺口清单（按"能不能把论文投出去"排序）

**阻断级（不补就无法成稿）：**

1. **跑分表缺「框架」列** —— ADR-0002 明确要求。跨栈比较（`CPU 78.9 ms` vs `NPU 6.02 ms`）是全项目最容易被审稿人攻的点，必须每张表都标 MindSpore Lite / ncnn / CANN。
2. **前期数据与新增数据未分离标注** —— ADR-0001 后果第一条。哪些数字来自 `ShusenPaper`、哪些是本轮新增，必须逐表声明，否则构成重复计数。
3. **`lpr-showcase` 未备份** —— 论文要引用的真值集、原始日志、旧稿都在里面。
4. **图表为零** —— 旧论文稿的 7 张图属于旧主张（保真/移植），不能直接搬。需要新画：流水线架构图、落点自证日志格式、算子覆盖对照图、T12/T13 的准确率与错误位分布、RQ4 时间线、C8 剂量-反应曲线。

**重要级（影响论文强度，但不阻断成稿）：**

5. **RQ4 只跑到 6 分钟 / thermal=1** —— 协议要求 20 分钟 / 80 轮，且要触发 thermal 2→3 台阶。补跑成本极低（自有设备 + 20 分钟），**收益极高**：这是 RQ4 唯一的头条结论来源。
6. **"融合携带"是相关而非因果** —— ADR-0002 未完成动作 1：需要同权重、仅改变算子孤立性的对照模型。这是审稿人最可能要求补的实验。
7. **双层黄牌 / 港澳两地牌未测** —— ADR-0006 未完成动作 1。属于"如实报告未测"，不阻断。
8. **绿牌集省份仍偏斜（皖 60%）** —— T13 边界已如实标注，论文里必须跟着说。

**可选级（求职/展示价值高，学术价值低）：**

9. 落点面板在 App 内落地（ADR-0003 未完成动作 2）—— **对演示页/视频价值高**。
10. 纯前端零安装演示页（spec user story 54）—— **对求职价值最高的一项**。
11. 网页证据仪表盘（spec user story 53）。

---

## 2. 论文该写什么

### 2.1 主张（一句话）

> **在一台不暴露 NPU 利用率的国产工艺移动 NPU 上，如何证明异构后端真的被用上、
> 以及"该不该换后端"这个问题的答案如何被分层。**

三根支柱（对应 ADR-0002，但已按 T6–T14 的实测重写）：

| # | 贡献 | 最硬的证据 | 成熟度 |
|---|---|---|---|
| C1 | **落点自证方法学**：在利用率物理不可读的平台上，用 `req=` / `LANDED=` / `fallback=` + 张量指纹 + CPU 对照差分三者互证 | T7 的 padding 缺陷被 `l2` 指纹忠实记录、且能区分"输入变了"与"后端变了" | 成熟，**但须包含 ADR-0003 的那次自我更正**（指纹是错标报警器，不是落点判据） |
| C2 | **算子覆盖边界是 模型 × 工具链 的联合属性** | 同一批 51 个探针，NNRT 部分被拒、CANN 51/51 全通过；`convtranspose` 在一侧连模型都产不出来 | 成熟 |
| C3 | **落点敏感性的分层答案**（本文最有实用价值的一条） | rec 落点改变输出 0%、det 0.1%（真实场景 n=1000）；但后端本身是准确率变量（+3.2 pp, p<0.0001）；而**牌长的影响（−6.6 pp）比落点大一个数量级** | 成熟 |

**建议把 T6 的"错误形态学"作为 C3 的支撑小节，而不是独立贡献**——它是一个漂亮的
否定结果转正（"偏斜不抬高准确率，只决定错误落在哪一位"），但单独成条偏薄。

### 2.2 章节骨架（英文稿，IEEEtran conference）

```
I.   Introduction
     - 动机：移动端 NPU 评测文献覆盖骁龙/天玑/苹果，国产工艺达芬奇无公开系统数据
     - 问题：请求 NPU 却静默回落；落了 NPU 也不一定快（13.11× → 0.98×）；
             算错了没有错误码；利用率读不到
     - 贡献 C1 / C2 / C3（三条，每条一句）
II.  Background & Related Work
     - 移动端 on-device 评测：MELTing Point [1]（LLM，Android/iOS/Jetson，不含国产 NPU）
     - 移动 NPU 异构调度与后端选择
     - 中文车牌识别基准：CCPD [2] / CCPD2020-Green [2]
     - 本文位置：不是又一个"加速比排行榜"，而是"可判定性"与"可证伪性"
III. Platform & Measurement Protocol
     - 设备、栈（MindSpore Lite 2.6.0 NDK → NNRT → NPU）
     - 测量协议：warm-up 10 + 100 次取 p50、≥5 轮、Fisher-Yates 洗牌、
       热态/充电/SOC 逐轮记录、checksum 校验
     - **落点自证协议**（本文方法学核心）：字段定义 + 三件套互证 + 边界
IV.  Operator Coverage Boundary (C2)
     - 36 算子三信号矩阵（NNRT 通路）：独立可编译 20 / 被拒 16
     - 51 探针 CANN 对撞：51/51 全通过
     - "独立委托 vs 融合携带"模型 + 其解释力 + **明确声明是相关性**
V.   Pipeline Case Study: Chinese LPR (RQ3, C3)
     - 四级流水线架构与分段预算
     - 落点 A/B 结果（T12/T13 的 n=1000）
     - 配对检验（T14）：分歧率低 ≠ 无偏
     - 错误的形态学（T6/T11/T12/T13 四次一致：省份位是主战场）
     - 牌长 vs 落点：谁更该盯
VI.  Sustained-Load Behaviour (RQ4)
     - 25 轮时间线、CPU/NPU 分列方差、指纹恒定
     - **如实写：未触发 thermal≥3，核心问题未答**
VII. Discussion & Threats to Validity
     - 跨栈可比性声明（每张表带「框架」列）
     - 隔离基准 ≠ 流水线内成本（C8：7.4 ms vs 19.5–31.6 ms）
     - 哪些数字继承自前期工作
VIII.Conclusion & Future Work（RQ2 跨 SKU 降级）
```

### 2.3 必须写进论文的"诚实边界"

这一节不能省，而且**是这篇论文的差异化优势**——它证明作者知道自己的边界在哪：

- NPU 利用率**物理上不可读**，全文禁止任何利用率数字。
- `L2asFp16` 指纹证明"这个后端算过"，**不证明"算得对"**。
- 融合携带模型目前是**相关性**，不是因果。
- T10/T11 的头条结论**已被 T12/T14 推翻**——论文只写更正后的版本，但可在 Discussion 里把"我们推翻了自己两次"当作方法学收获来讲。
- RQ4 未触发降频台阶。
- 省份偏斜在绿牌集上**无法消除**。
- 跨栈比较只能当量级参考。

---

## 3. 语言策略：中文、英文，还是双语？

### 3.1 结论

**不要写成"中英双语混排"的一篇。要做成"一份内容源 → 两个独立语言版本"，
英文版为主稿（投稿用），中文版为并行稿（中文期刊 / 学位论文 / 求职用）。**

你已经有现成先例：`lpr-showcase/paper/` 下同时存在 `latex-en/main.tex`（47 KB）
与 `latex-zh/main.tex`（42 KB），都是 IEEEtran 类，各自独立编译。这个结构是对的，
继续沿用。

### 3.2 为什么不能混排

| 维度 | 英文稿 | 中文稿 |
|---|---|---|
| 目标读者 | 国际同行评议 | 国内评审 / 答辩 / 招聘方 |
| 篇幅 | 会议 6–8 页、期刊 10–14 页 | 通常 8000–12000 字，篇幅逻辑不同 |
| 论证习惯 | 主张先行、证据紧跟、越短越好 | 铺垫与背景说明占比更高 |
| 术语 | `landing self-evidencing`（需定义） | 「落点自证」（`CONTEXT.md` 已定义） |
| 引用体例 | IEEE numbered `[1]` | 多数中文刊要求 GB/T 7714 |

把两种规范塞进一份稿子，结果是两边都不合格——**中文期刊通常不接受英文正文，
国际会议不接受中文正文**，所以"混排"在投稿意义上没有出口。

### 3.3 但不要"先写中文再翻译"

翻译体会被审稿人一眼看出（被动语态堆叠、连接词直译、"基于……的方法"直译成
"method based on"）。正确做法：

> **先定英文稿（结构与论证按国际惯例），再按中文写作习惯重写中文版。
> 是"重写"，不是"翻译"。** 同一批数字、同一批图，但句子结构、段落节奏、背景
> 铺垫的长度都重新组织。

### 3.4 实际执行建议

1. **只维护一份"数字与图表源"**（见 §7 的一致性表），两个语言版本都从它取数——
   这样不会出现中英稿数字打架。
2. **先出英文 arXiv 预印本**。零门槛、可被引用、可挂 GitHub 链接，而且**正好
   满足求职需求**（见 §7）。
3. **中文稿同步推进**，目标定为中文期刊或作为学位论文的章节骨架。

---

## 4. 格式：要不要写成 IEEE？

### 4.1 结论

**用 IEEEtran，但先用 `conference` 模式，不要一开始就锁死投稿目标。**

### 4.2 理由

IEEEtran 是 IEEE 官方 LaTeX 文档类（作者 Michael Shell，CTAN 与 IEEE Author Center
同步分发）[[3]](https://journals.ieeeauthorcenter.ieee.org/?p=5166)[[4]](https://ewh.ieee.org/conf/ius_2008/z_mexample/latex01_latex_letter5march2007.pdf)，
通过文档类选项切换格式：

```latex
\documentclass[conference]{IEEEtran}   % 会议稿：6–8 页，无作者简介
\documentclass[journal]{IEEEtran}      % 期刊/Transactions：10–14 页，双栏
\documentclass[journal,draftcls,onecolumn]{IEEEtran}  % 部分期刊的评审稿
```

**为什么先用 `conference`：**

1. **它逼你把贡献压缩清楚**。6–8 页的硬约束会暴露"哪条贡献其实撑不起来"。
   你现在有 C1/C2/C3 三条 + T6 的形态学，用 conference 篇幅一压，
   就能判断 T6 该不该独立成条。
2. **改成 journal 只是换一个选项**，正文可以扩写，不用重写。
3. **旧稿已经用了 IEEEtran**（`latex-en/main.tex`），工具链和字体问题都趟过了。

### 4.3 但别把 IEEE 当成唯一出口

按这篇工作的性质（系统测量 + 方法论 + 应用级案例），可选路径有三条，
**建议先做路径 A，再决定 B/C**：

| 路径 | 目标 | 优点 | 代价 |
|---|---|---|---|
| **A. arXiv 预印本（英文）** | 无审稿 | 一周内可上线，立刻可用于求职/网页/GitHub | 无同行评议背书 |
| B. 英文期刊 / 会议 | 如 IEEE Access（OA、周期相对可控）、移动系统/嵌入式方向会议 | 正式发表 | 周期长、审稿要求补实验（尤其 RQ4 与融合携带因果） |
| C. 中文期刊 | 工程应用类（如《计算机工程与应用》《计算机应用研究》《小型微型计算机系统》）或更高档（《软件学报》《计算机学报》） | 国内认可度高、对"国产 NPU"选题友好 | 中文刊对"系统测量类"接受度因刊而异，需按目标刊的投稿指南核对 |

> ⚠️ **投稿前必做**：用 IEEE 官方的 Publication Recommender 与 Template Selector
> 确认目标刊/会的**具体模板与页数要求**——不同刊（如 Computer Society 系列、
> IEEE Access）的模板有额外差异，用错模板是常见的直接退稿原因[[3]](https://journals.ieeeauthorcenter.ieee.org/?p=5166)。

---

## 5. GitHub 开源怎么写

### 5.1 现状的三个问题

1. **仓库分散且全部 private** —— 四个仓库（`lpr-kirin8020` / `lpr-kirin8020-app` /
   `shusen-npu-characterization` / `lpr-harmony`），外人不知道该看哪个。
2. **`lpr-showcase` 无 git** —— 证据层没有版本控制，也没备份。
3. **仓库内容是"给自己看的"，不是"给读者看的"** —— 现在打开 `lpr-kirin8020`
   第一眼是 `CONTEXT.md` 和 ADR，**没有 README**。招聘方和审稿人第一眼就流失。

### 5.2 仓库规划（建议）

```
lpr-kirin8020          ← 旗舰仓库（论文 + 证据 + 文档），对外的主入口
  README.md            ← 新增，面向读者
  docs/adr/            ← 已有
  docs/notes/          ← 已有（19 篇实验笔记，这是最强资产）
  paper/               ← 新增：论文稿（en / zh）+ 图
  figures/             ← 新增：统一出图源（脚本 + 产物）
  evidence-index.md    ← 新增：数字 → 证据文件的索引表

lpr-kirin8020-app      ← App 实现，README 里 link 回旗舰仓库
lpr-showcase           ← 先建 git 推私库；证据与数据集索引（大文件不入库）
lpr-harmony            ← 保留为"重写前的参考基线"，README 里说明关系
shusen-npu-characterization  ← 保留为前期工作，README 里互相 link
```

### 5.3 开源前的合规清理（**这一步不做完不要转 public**）

| 项 | 风险 | 处理 |
|---|---|---|
| 华为 DDK / OMG 工具链 | 不可再分发 | 保持 `.gitignore` 排除，只留文档化的获取步骤（`docs/notes/toolchain-and-sources-on-disk.md` 已写好） |
| `.ms` / `.om` 产物 | 已排除 | 确认 `.gitignore` 覆盖 `models_ms/`、`models_om/`、`models_om_ops/` |
| 模型权重许可 | 识别器/检测器为 Apache-2.0 系 | 在 README 的 License 一节逐项列出并附上游链接 |
| CCPD / CCPD-Green 数据集 | 学术用途，**不可再分发** | 只写获取步骤与抽样脚本（`tools/ccpd_select*.py`），不打包图片；App 内的 rawfile 抽样图**要从开源版移除** |
| 华为工单往返（三缺陷提单链） | 可能含保密条款 | **脱敏**：只保留结论与技术细节，去掉工单号、联系人、内部截图 |
| 绝对路径 | 泄露本机目录结构 | 全仓库搜 `<HOME>`、`<DEVECO_HOME>`、`Desktop\`，替换为占位符 |
| 个人邮箱 / 账号 | 隐私 | 检查 `git config user.email`、脚本里的硬编码地址 |

> 另注：`_hw_nodes.csv`（1.2 MB）与 `_hw_tree.json`（1.26 MB）是华为文档站的抓取产物。
> **这类站点地图数据开源前建议移除**——它不构成论文证据，但可能触及站点条款。

### 5.4 README 骨架（可直接改填）

```markdown
# Landing Self-Evidencing on a Domestic-Process Mobile NPU
### A Chinese license-plate recognition pipeline on Kirin 8020

[English](README.md) | [中文](README.zh-CN.md)

## What this is
A measurement instrument disguised as a license-plate recognition app.
On HarmonyOS, NPU utilisation is **physically unreadable** — not via
DevEco Profiler, not via SP_daemon, not via hdc. So how do you prove the
heterogeneous backend was actually used?

Every inference in this project logs `req=` / `LANDED=` / `fallback=` plus
an output-tensor fingerprint, so backend placement is *read from raw logs*
instead of asserted.

## Three findings
1. **Landing self-evidencing** — …（一句话 + 数字）
2. **Operator support is a model × toolchain joint property** —
   51/51 operator probes pass on the CANN toolchain, including ones NNRT
   rejects; `ConvTranspose` cannot even be *converted* on the NNRT side.
3. **Which knob actually matters** — switching the recogniser's backend
   changes 0 % of outputs (n=1000 real vehicle images); plate length costs
   −6.6 pp (8-char new-energy 92.5 % vs 7-char 99.1 %).

## Headline numbers
| Quantity | Value | Conditions | Evidence |
|---|---|---|---|
| … | … | thermal / build / n | `evidence/…` |

## What we deliberately do NOT claim
- No NPU utilisation figure — the platform does not expose one.
- The tensor fingerprint proves *a backend computed*, not that it computed
  *correctly*.
- "Fusion carry-over" is currently a correlation, not a causal claim.
- Cross-stack comparisons (MindSpore Lite vs ncnn vs CANN) are
  order-of-magnitude only. Every benchmark table carries a Framework column.

## Layout
- `docs/adr/` — decisions, including three where we overturned ourselves
- `docs/notes/` — 19 raw experiment logs
- `paper/` — manuscript (EN / ZH)
- `evidence-index.md` — every number → the file it came from

## Reproduce
…（构建 + 跑协议的最小步骤）

## License / Acknowledgements
…（逐项列模型与数据集许可）
```

**关键设计**：README 里必须有一节 **"What we deliberately do NOT claim"**。
这个项目的可信度恰恰来自它反复推翻自己（T10→T12、T11→T14、ADR-0003 更正、ADR-0005 更正三次）。
**把"诚实边界"当卖点写，比堆数字更能打动技术面试官。**

---

## 6. 个人网页展示

### 6.1 建议做"一个项目页"，不是一整站

单页结构（自上而下）：

| 区块 | 内容 | 素材来源 |
|---|---|---|
| Hero | 一句话主张 + 一张流水线架构图 | 需新画 |
| 三个数字 | 0 %（rec 落点分歧）/ 51⁄51（CANN 准入）/ −6.6 pp（牌长代价） | T12 / T8 / T13 |
| 问题陈述 | "请求了 NPU，日志里不写；落了 NPU，也不一定快" | `spec.md` Problem Statement |
| 方法 | 落点自证三件套的**真实日志片段**（截图或代码块） | T7 的 `RQ4P` 行 |
| 关键发现 | 4–6 张卡片，每张一个结论 + 一个数字 + 一个"边界" | T6–T14 |
| **自我更正时间线** | T10→T12、T11→T14、ADR-0003/0005 的更正记录 | `docs/notes/` |
| 证据 | 链接到 GitHub 上的 `evidence/` 与 `docs/notes/` | — |
| 论文 | arXiv 链接 + 中文稿 PDF | — |
| 演示 | 纯前端零安装 Demo（spec user story 54） | 需新做 |

### 6.2 "自我更正时间线"是这一页最该突出的东西

大多数求职作品集展示"我做成了什么"。你手上有更稀缺的东西：
**同一批数据上，我先得出 A 结论，再用配对检验推翻它，并保留了推翻的过程**。
这对招聘方的信号价值远高于任何加速比数字。

### 6.3 实现建议

- **静态页 + GitHub Pages** 即可，不需要后端。
- 若要零安装 Demo：把识别器的预处理 + 推理做成 WASM/ONNX-Runtime-Web，
  跑在浏览器里——`lpr-showcase` 里已有**纯前端 WASM 演示代码**，可以直接复用。
- 若想省事：你的 `MeiRiShiZheng` 用的 Astro + Cloudflare Workers 栈可以直接
  挪一个页面过来，设计令牌也是现成的。

---

## 7. 求职项目经历怎么写

### 7.1 先立一张"数字一致性表"（写简历/网页/论文前必须先定这个）

spec 的 user story 47 要求"所有性能数字都能追到一个证据文件，论文/简历/网页三者一致"。
**这张表就是那个唯一来源**，三个出口都从它取数：

| 数字 | 值 | 必须一并标注的条件 | 证据 |
|---|---|---|---|
| 识别器 NPU vs CPU 加速 | **4.46×** | 同栈内（MS Lite）、热态、n=961/993（非空子集） | T11 |
| 端侧 NPU vs 主机准确率 | **−0.7 pp**（显著） | 配对 McNemar p=0.0156，0:7 | T14 |
| 后端对准确率的影响 | **+3.2 pp**（NPU 优于 CPU） | 同预处理、同模型、p<0.0001 | T14 |
| 真实场景全流水线准确率 | **99.1%** | CCPD1000，n=1000，7 字符 | T12 |
| 8 字符新能源牌准确率 | **92.5%** | 皖占 60%，n=1000 | T13 |
| 牌长代价 | **−6.6 pp** | 逐省对照已排除省份构成 | T13 |
| rec / det 落点分歧率 | **0% / 0.1%** | 真实整车场景，n=1000 | T12 |
| CANN 算子准入 | **51/51** | 含 NNRT 侧被拒的 9 个 | T8 |
| 检测段 / 识别段占帧预算 | **49% / 10%** | 生产档，检出帧 40 ms | 相机路 |
| 隔离基准 vs 流水线内 | **7.4 ms vs 19.5–31.6 ms** | 同模型同后端同线程数 | C8 |
| RQ4 端到端 p50 | **82.1 ms** | 25 轮，thermal=1，未充电 | T7 |

**禁止出现在任何出口的数字**：任何 NPU 利用率（ADR-0003）。

### 7.2 简历条目（中文，可直接粘贴）

> **麒麟 8020 端侧异构推理与车牌识别流水线** ｜ 独立完成 ｜ 2026.08–2026.09
>
> - 在 HarmonyOS 6 + MindSpore Lite/NNRT 上实现中文车牌识别四级流水线（检测 → 透视矫正 →
>   识别 → 判色），以 **ncnn-Vulkan 与 CANN 双工具链**做跨栈对照。
> - 设计**落点自证协议**：在 NPU 利用率物理不可读的平台上，用 `req=` / `LANDED=` /
>   `fallback=` 三字段 + 输出张量指纹，让后端落点**从原始日志直接读出**而非由参数推定；
>   该协议成功捕获一个纯预处理缺陷（输出层不可见，仅指纹可见）。
> - 在 1000 张真实整车图上做后端 A/B：识别器换后端改变 **0%** 输出、检测器 **0.1%**；
>   但配对 McNemar 证明**后端本身是准确率变量**（NPU vs CPU **+3.2 pp**，p<0.0001）——
>   "分歧率低 ≠ 无偏"。**牌长的影响比落点大一个数量级**（8 字符新能源 92.5% vs 7 字符 99.1%）。
> - 证明 **NPU 支持性是「模型 × 工具链」的联合属性**：同一批 51 个算子探针，NNRT 侧部分被拒，
>   CANN 侧 **51/51 全通过**（含 `ConvTranspose`——它在 NNRT 侧连模型都产不出来）。
> - 用剂量-反应 + 忙等对照 + 线程数对照三组实验，把「隔离基准 7.4 ms vs 流水线内 19.5–31.6 ms」
>   的 2 倍差距定位为 **DVFS + 线程池唤醒**两个叠加机理。

### 7.3 Resume entry (English, ready to paste)

> **On-Device Heterogeneous Inference on a Domestic-Process Mobile NPU** · Solo · 2026
>
> - Built a 4-stage Chinese license-plate recognition pipeline (detect → rectify →
>   recognise → colour) on HarmonyOS 6 over MindSpore Lite → NNRT → DaVinci NPU,
>   with ncnn-Vulkan and CANN as cross-toolchain controls.
> - Designed a **landing self-evidencing protocol** for a platform where NPU
>   utilisation is physically unreadable: every inference logs `req=` / `LANDED=` /
>   `fallback=` plus an output-tensor fingerprint, so backend placement is *read from
>   raw logs* rather than asserted. The protocol caught a pre-processing defect that
>   was invisible at the output layer.
> - Ran backend A/B over 1,000 real vehicle images: switching the recogniser's backend
>   changes **0 %** of outputs and the detector's **0.1 %** — yet a paired McNemar test
>   shows the backend *is* an accuracy variable (**+3.2 pp**, p < 0.0001). Plate length
>   matters an order of magnitude more (**92.5 %** for 8-char new-energy vs **99.1 %**
>   for 7-char, province-matched control).
> - Proved NPU supportability is a **model × toolchain joint property**: the same 51
>   operator probes that NNRT partly rejects pass **51/51** through the CANN toolchain,
>   including `ConvTranspose`, which cannot even be converted on the NNRT side.
> - Localised a **2× gap between isolated microbenchmarks and in-pipeline cost**
>   (7.4 ms vs 19.5–31.6 ms) to DVFS plus thread-pool wake-up latency, using a
>   dose–response sweep with spin-wait and thread-count controls.

### 7.4 面试会被追问什么，你手上有哪些证据

| 可能被追问 | 你的答案 | 证据在哪 |
|---|---|---|
| "怎么证明真的用了 NPU？" | `LANDED=` 字段 + 张量指纹 + CPU 对照差分 | `docs/adr/0003`、T7 |
| "利用率多少？" | **平台不暴露，我不编数字** | `docs/adr/0003` 边界声明 |
| "换后端结果会变吗？" | 真实场景 0%/0.1%；但配对检验显示后端是准确率变量 | T12、T14 |
| "那到底该优化什么？" | 不是 NPU——检测段占帧预算 49%，识别段只占 10% | `camera-npu-headroom.md` |
| "有没有失败/被推翻的结论？" | 有三次：T10→T12、T11→T14、ADR-0003 的指纹判据 | `docs/notes/` |
| "为什么不做跨芯片对比？" | 门店演示机渠道不可控，已降级为未来工作并说明约束 | `docs/adr/0007` |

**"有没有被推翻的结论"这一题是你的加分项**——大多数候选人答不出来。
你的仓库里有完整的三次自我更正记录，这是**可验证的科研诚信证据**。

---

## 8. 执行顺序（建议）

按"投入产出比"排序，前四项做完就足以支撑求职：

| 优先级 | 事项 | 预估成本 | 产出 |
|---|---|---|---|
| **P0** | `lpr-showcase` 建 git + 推私库 | 半小时 | 解除唯一的数据丢失风险 |
| **P0** | 定"数字一致性表"（§7.1） | 1 小时 | 论文/简历/网页三者同源 |
| **P0** | 补跑 RQ4 到 20 分钟 / 80 轮 | 半天（含构建） | 补上 RQ4 唯一的头条结论 |
| **P1** | 出英文稿（IEEEtran conference） | 数天 | 论文主体 |
| **P1** | 画 6 张图（架构、日志格式、算子对照、准确率与错误位、RQ4 时间线、C8 曲线） | 1–2 天 | 论文与网页共用 |
| **P1** | 旗舰仓库 README + 合规清理 → 转 public | 1–2 天 | 对外主入口 |
| **P2** | 中文稿 | 数天 | 中文期刊 / 学位论文 |
| **P2** | 个人项目页 + 零安装 Demo | 2–3 天 | 求职主入口 |
| **P3** | 融合携带因果实验（同权重、逐算子插桩对照） | 数天 | 应对审稿意见 |

**如果时间只够做三件事**：P0 三项 + README。因为**论文可以晚，但证据不能丢、
数字不能乱、README 不能没有**。

---

## 参考文献

[1] S. Laskaridis, K. Katevas, L. Minto, and H. Haddadi, "MELTing Point: Mobile Evaluation of Language Transformers," in *Proc. 30th Annual Int. Conf. Mobile Computing and Networking (MobiCom '24)*, 2024, pp. 890–907. https://doi.org/10.1145/3636534.3690668

[2] Z. Xu, W. Yang, A. Meng, N. Lu, and H. Huang, "Towards End-to-End License Plate Detection and Recognition: A Large Dataset and Baseline," in *Proc. European Conf. Computer Vision (ECCV)*, 2018, pp. 255–271.

[3] IEEE Author Center, "Tools for IEEE Authors." https://journals.ieeeauthorcenter.ieee.org/?p=5166

[4] M. Shell, "IEEEtran LaTeX Class Documentation," IEEE / CTAN. https://ewh.ieee.org/conf/ius_2008/z_mexample/latex01_latex_letter5march2007.pdf
