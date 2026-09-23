# 简历条目（新主张版，中英双语）

> **本文取代 `lpr-showcase/resume/resume-bullets.md`**（那一版是旧主张「跨语言移植保真」，
> 其准确率结论已被 T14 推翻、论文主张已被 ADR-0002 归档）。
> 旧版仍在原处存档，作为前期成果引用。
>
> **使用原则**：每个数字都必须能在面试中当场复现，且与论文、README、网页**同源** ——
> 全部取自 [`docs/evidence-index.md`](evidence-index.md)，
> 由 `lpr-kirin8020-app/tools/verify_published_numbers.py` 机检（91 项）。
>
> **禁止出现在任何出口的数字**：NPU 利用率（平台不暴露，ADR-0003）。

---

## 一、中文版

### 标准版（5 条）

**麒麟 8020 端侧异构推理：落点自证方法学与车牌识别流水线** ｜ 独立完成 ｜ 2026.08–2026.09

- 在 HarmonyOS 6 + MindSpore Lite/NNRT 上实现中文车牌识别四级流水线（检测 → 透视矫正 →
  序列识别 → 像素判色），并以 **ncnn-Vulkan 与 CANN 两条独立工具链**做跨栈对照。

- 设计**落点自证协议**：在 NPU 利用率**物理不可读**的平台上（应用侧与设备调试 shell
  都不暴露计数器），用 `req=` / `LANDED=` / `fallback=` 三字段 + 输出张量指纹 +
  CPU 对照差分，让后端落点**从原始日志直接读出**而非由参数推定。
  该协议捕获了一个纯预处理缺陷 —— 输出层只表现为"少一个字符"，仅指纹可见。

- 在 **1000 张真实整车图**上做后端 A/B：换识别器后端改变 **0%** 输出、换检测器 **0.1%**；
  但**配对** McNemar 证明**后端本身就是准确率变量**（NPU vs CPU **+3.2 pp**，p<0.0001，
  配对 38:6）——「分歧率低 ≠ 无偏」。**而牌长的代价比落点大一个数量级**
  （8 字符新能源牌 92.5% vs 7 字符 99.1%，**−6.6 pp**，逐省对照已排除省份构成）。

- 证明 **NPU 支持性是「模型 × 工具链」的联合属性，不是硬件属性**：同一批 51 个算子探针，
  NNRT 侧 36 个里有 16 个单独构图被拒（含 ReLU / Softmax / MaxPool），
  CANN 侧 **51/51 全部通过** —— 含 `ConvTranspose`，它在 NNRT 侧**连模型都转换不出来**。
  并把这条从探针推到**生产阶段**：为把车辆检测从 CPU 挪到 NPU，同一任务换架构 ——
  ultralytics `v5-u`（含 DFL）**转换即失败**；原版 anchor-based YOLOv5 在**裁掉解码头**
  （把 sigmoid 与 anchor 解码移到 Host）之后静态门全过、真机落 NPU
  （裸头 5.39 ms vs 同栈 CPU 42.02 ms，**7.79×**），且裁切经**逐元素比对自证语义未变**
  （相对误差 1.9e-5）。**同一任务、同一工具链、两种架构 —— 一种被拒、一种准入。**

- 用**剂量-反应 + 忙等对照 + 线程数对照**三组实验，把「隔离基准 7.4 ms vs 流水线内
  19.5–31.6 ms」的 2 倍差距定位为 **DVFS 频率 + 线程池唤醒**两个叠加机理；
  并实测**持续负载 23.3 分钟下延迟漂移 +26.9%，而热档全程未变** ——
  推翻「热档不变即性能稳定」的假设。

### 精简版（3 条）

- 在麒麟 8020（HarmonyOS 6 + MindSpore Lite/NNRT）上实现中文车牌识别四级流水线，
  并设计**落点自证协议**：在 NPU 利用率不可读的平台上，用 `req=` / `LANDED=` /
  `fallback=` + 张量指纹 + CPU 差分，让后端落点从原始日志直接读出。

- 1000 张真实整车图上的后端 A/B：换后端改变 0%（识别器）/ 0.1%（检测器）输出，
  但配对检验显示**后端是准确率变量**（+3.2 pp，p<0.0001）；
  **牌长代价大一个数量级**（8 字符 92.5% vs 7 字符 99.1%）。

- 证明 NPU 支持性是**模型 × 工具链**的联合属性：NNRT 侧 16/36 算子单独构图被拒，
  CANN 侧 51/51 全通过。并把这条推到生产阶段：同一任务换架构后，一种**转换即失败**、
  一种裁掉解码头后**真机落 NPU**（裸头 5.39 vs 42.02 ms，**7.79×**）。

### 技能标签

```
端侧推理    MindSpore Lite · NNRT · NPU 委托与回落 · CANN/OMG · ncnn-Vulkan
系统测量    落点自证 · 张量指纹 · 延迟分解 · 热特性 · 背压识别 · 配对检验(McNemar)
视觉        YOLO 检测 · 透视矫正 · CRNN/CTC · NMS · 像素级颜色测量
工程        C++/NAPI · ArkTS · HarmonyOS API 24 · Python 工具链
验证方法    证据文件化 · 数字守卫（可机检）· 负结果落盘 · 自我更正留痕
```

---

## 二、English version

### Standard (5 bullets)

**On-Device Heterogeneous Inference on a Domestic-Process Mobile NPU** · Solo · 2026

- Built a four-stage Chinese licence-plate recognition pipeline (detection → perspective
  rectification → sequence recognition → pixel-based colour determination) on HarmonyOS 6
  over MindSpore Lite → NNRT → DaVinci NPU, with **ncnn-Vulkan and CANN as two independent
  cross-toolchain controls**.

- Designed a **landing self-evidencing protocol** for a platform where NPU utilisation is
  **physically unreadable** (not exposed to applications, nor to the on-device debug shell):
  every inference logs `req=` / `LANDED=` / `fallback=` plus an output-tensor fingerprint
  and a CPU differential, so backend placement is **read from raw logs** rather than
  asserted from configuration. The protocol caught a pure pre-processing defect that was
  invisible at the output layer — its only symptom was a plausible-looking plate string
  missing one character.

- Ran a backend A/B over **1,000 real vehicle images**: switching the recogniser's backend
  changed **0 %** of outputs and the detector's **0.1 %**. Yet a **paired** McNemar test
  shows the backend *is* an accuracy variable (**+3.2 pp**, p < 0.0001, discordant 38:6) —
  *low divergence does not imply absence of bias*. **Plate length costs an order of
  magnitude more**: **92.5 %** for eight-character new-energy plates against **99.1 %** for
  seven-character plates (**−6.6 pp**, province-matched control).

- Proved that **NPU supportability is a model × toolchain joint property, not a hardware
  property**: of 36 single-operator probes, 16 are rejected when compiled standalone on the
  NNRT path (including `ReLU`, `Softmax`, `MaxPool`), while the CANN path passes **51/51** —
  including `ConvTranspose`, which **cannot even be converted** on the NNRT side. Carried
  this from probes to a **production stage**: to move vehicle detection off the CPU, the same
  task was re-architected — ultralytics `v5-u` (DFL head) **fails conversion outright**,
  whereas the original anchor-based YOLOv5 clears the static gates once its decode head is
  cut away (sigmoid and anchor decoding moved to the host) and then lands on the NPU
  (**5.39 ms** bare head vs **42.02 ms** on the same stack's CPU, **7.79×**). The cut was
  shown to be semantics-preserving by element-wise comparison (relative error 1.9e-5).
  *Same task, same toolchain, two architectures — one rejected, one admitted.*

- Localised a **2× gap between isolated microbenchmarks and in-pipeline cost** (7.4 ms vs
  19.5–31.6 ms) to DVFS frequency scaling plus thread-pool wake-up latency, using a
  dose–response sweep with busy-wait and thread-count controls; and measured **+26.9 %
  latency drift over 23.3 minutes of sustained load with the thermal level unchanged**,
  refuting the assumption that a stable thermal level implies stable performance.

### Condensed (3 bullets)

- Built a four-stage Chinese licence-plate recognition pipeline on Kirin 8020 (HarmonyOS 6,
  MindSpore Lite → NNRT), and designed a **landing self-evidencing protocol** that makes
  backend placement readable from raw logs on a platform that exposes no NPU utilisation
  counter.

- Over 1,000 real vehicle images, switching a role's backend changed 0 % (recogniser) and
  0.1 % (detector) of outputs — but a paired test shows the backend is an accuracy variable
  (**+3.2 pp**, p < 0.0001), and plate length costs an order of magnitude more
  (8-char 92.5 % vs 7-char 99.1 %).

- Proved NPU supportability is a **model × toolchain** joint property: 16/36 operators are
  rejected standalone on NNRT while **51/51** pass on CANN. Carried it to a production
  stage: the same task re-architected — one model **fails conversion**, the other lands on
  the NPU once its decode head is cut (**5.39** vs **42.02 ms** bare head, **7.79×**).

---

## 三、面试口径（务必先读）

| 面试官可能问 | 应当如何回答 |
|---|---|
| 「NPU 利用率多少？」 | **平台不暴露，我不编数字。** 应用侧不行、`hdc` 侧也不行，唯一相关的计数器是温度不是负载。我用的替代证据是三个：落点字段、延迟差、张量指纹。这是 ADR-0003 立的规矩。 |
| 「怎么证明真的跑在 NPU 上？」 | `LANDED=` 字段直接从日志读出来，配 `req=` 与 `fallback=` 区分"我选的"和"回落的"。指纹只用来抓 dtype 错标，**不用来判落点** —— 我一开始搞错了这一点，实测证伪后改了。 |
| 「换后端结果会变吗？」 | 真实整车场景下 0%（识别器）/ 0.1%（检测器）。但**配对检验显示后端是准确率变量**（+3.2 pp，p<0.0001）—— 分歧率低不等于无偏，0.1% 的分歧如果方向一致，在 1000 张上就累积成显著差异。 |
| 「那到底该优化什么？」 | **不是 NPU。** 帧预算分解显示检测段（CPU）占 49%，识别段（NPU）只占 10%。把 NPU 压到 0 也救不回缺口。"榨干 NPU"在这条流水线上问错了对象。 |
| 「有没有被推翻的结论？」 | **有三次**，而且更正记录留在仓库里：T10→T12（"检测器才是敏感环节"是裁剪图工况的产物）、T11→T14（"移植保真"被配对检验推翻）、ADR-0003（张量指纹判据被真机证伪）。 |
| 「加速比多少？」 | 识别器同栈内 **4.46×**（16.78 ms → 3.76 ms，n=961/993）。**跨栈的我不报** —— NPU 走 MindSpore Lite、GPU 只有 ncnn-Vulkan、CPU 有两套，只有同栈比值可比。 |
| 「为什么不做跨芯片对比？」 | 需要门店演示机，热态与充电状态不可控，且协议要求同一 HAP —— 一次行程失败全部作废。已按 ADR-0007 降级为未来工作并说明约束。 |
| 「模型是你训练的吗？」 | **不是，也不训练。** 用公开预训练权重（Apache-2.0 系）。我的贡献是测量方法学与端侧部署，不是模型。 |
| 「准确率 92.5% 是什么水平？」 | 那是 8 字符新能源牌，**且该集 60% 是皖**，偏斜无法用抽样消除。7 字符真实场景是 99.1%。**不要把它说成路况指标。** |

### 绝对不要说的话

- ❌「NPU 利用率 XX%」→ 平台不暴露，说了无法验证
- ❌「GPU 加速 N 倍」→ 实测三个模型在 Vulkan 上都比 CPU 慢；只能说「通路成立且数值保真」
- ❌「移植保真」→ 已被 T14 推翻（端侧比主机低 0.7 pp 且统计显著）
- ❌「检测器才是敏感环节」→ 已被 T12 推翻（那是裁剪图工况的产物）
- ❌「CANN 全通过所以 CANN 更快」→ 只证明准入边界；生产档实测 MS Lite 在识别器上更快
- ❌「融合携带已被证明」→ 目前是**相关性**，同权重逐算子插桩的因果实验**没做**
- ❌ 把 `1000/p50` 说成 fps → 那是**服务时间倒数**，不是帧率

---

## 四、数字速查卡（面试前扫一眼）

| 指标 | 值 | 条件 |
|---|---|---|
| 换后端后识别器输出变化 | **0%**（0/1000） | 真实整车场景 |
| 换后端后检测器输出变化 | **0.1%**（1/1000） | 同一批图、同一探针 |
| 识别器 NPU vs CPU | **4.46×** | 同栈；16.78 vs 3.76 ms，n=961/993 |
| 后端对准确率的影响 | **+3.2 pp**，p<0.0001 | 配对 McNemar，38:6 |
| 端侧 NPU vs 主机 | **−0.7 pp**，p=0.0156 | 配对，严格嵌套 0:7 |
| 真实场景全流水线 | **99.1%** | 7 字符，n=1000 |
| 8 字符新能源牌 | **92.5%** | n=1000，皖 60% |
| 牌长代价 | **−6.6 pp** | 逐省对照已排除省份构成 |
| 省份位占替换错误 | **49.3%**（33/67） | 等长行 n=971 |
| CANN 算子准入 | **51/51** | 含 NNRT 侧被拒的 9 个 |
| 车辆检测换架构后落点 | **NPU，无 fallback** | `NNRT:NPU_ohos…kirin8020_v2_0`，MIA-AL00 |
| 车辆检测裸头 NPU vs 同栈 CPU | **7.79×** | 5.39 vs 42.02 ms —— **仅裸头**，不含预处理/解码/NMS |
| 同一任务、两种架构的转换结果 | **1 被拒 / 1 通过** | v5-u（DFL）转换即失败；原版 v5 裁掉解码头后通过 |
| 帧预算：检测 / 识别 | **49% / 10%** | 生产档检出帧 |
| 隔离基准 vs 流水线内 | **7.4 vs 19.5–31.6 ms** | 同模型/后端/线程数 |
| 持续负载漂移 | **+26.9%** | 23.3 min / 80 轮，热档不变 |

---

## 五、一句话概括（自我介绍用）

> 我做的是一个中文车牌识别 App，但我更想聊的不是识别本身，而是**怎么在一个连
> NPU 利用率都读不到的手机上，证明这次推理真的跑在 NPU 上了** ——
> 我用三个日志字段加一个张量指纹把这件事变成可读的，然后拿它测出了三件事：
> 换后端几乎不改输出但确实是准确率变量、算子能不能上 NPU 取决于工具链而不是硬件、
> 以及这条流水线上真正吃帧预算的其实是 CPU 上的检测段而不是 NPU。
> 最后我把这个结论用回了工程：那一段要上 NPU，**必须换模型架构** ——
> 同一个任务，一种架构连转换都过不去，另一种裁掉解码头之后真机落 NPU、快 7.79×。
