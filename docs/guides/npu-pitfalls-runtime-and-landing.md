# NPU 调用指南（下）：运行时与落点类坑

> 这是**中文指南的第二半**。第一半是 [`npu-pitfalls-build-and-env.md`](npu-pitfalls-build-and-env.md)，
> 覆盖**构建与环境**（`-O3` 被废、中文路径、固定 batch、会话常驻）。
> 本文覆盖**运行时与落点**——模型能构建出来了，但**它到底跑在哪、跑得对不对、跑得快不快**这四类问题。
>
> 每条同样四段：**现象 → 根因 → 正确做法 → 可复现的最小验证**。
> 所有数字都取自 `docs/evidence-index.md` 与对应笔记，**没有一个是本文自造的**。
>
> **平台**：HUAWEI nova 14 Pro（MIA-AL00）· 麒麟 8020 · HarmonyOS 6.1.0.135 · API 24。
> 换平台请重新验证，本文的结论**不保证可迁移**。

---

## 阅读顺序建议

| 你现在的处境 | 看哪条 |
|---|---|
| 我不知道模型到底跑在 NPU 还是 CPU 上 | 坑 1 |
| 我用了 INT8，想不通为什么一点没变快 | 坑 2 |
| 同一个算子，一边能跑一边不能跑 | 坑 3 |
| 我想试试 GPU | 坑 4 |
| 我测出来很快，装进流水线却慢一倍 | 坑 5 |

---

## 坑 1 · NPU 利用率读不到：你必须改用「落点自证」

### 现象

你想证明「NPU 真被用上了」，于是去找利用率数字。你会发现**根本找不到**：

- DevEco Profiler 的 Realtime Monitor 能看 CPU、能看 GPU 利用率，**NPU 那一栏不存在**。
- SP_daemon（SmartPerf 的设备端 CLI）有 CPU 负载、有 `gpuFrequency` / `gpuLoad`，
  NPU 只有一个 **`npu_thermal`** —— 那是**温度**，不是负载。
- `hidumper` 只有 CPU 的 `--cpuusage` / `--cpufreq`；`hiperf` 只有 CPU 硬件计数器。

换句话说：**越是需要证明自己「榨干了 NPU」的人，越拿不到证据。**

### 根因

**这不是工具没找对，是平台没暴露这个计数器。**（ADR-0003 已把它作为一种**边界声明**记下来，
并明确写了「本结论基于官方文档与工具清单，不是对设备做过逆向尝试后的结论」。）

判断依据很简单：**同一份工具能报 GPU 利用率（实测 `gpuLoad=0.000000`）却不能报 NPU**。
如果是我们不会用，那应该两边都拿不到；只有一边拿得到，说明是平台侧没提供。

### 正确做法

**放弃利用率，改用「落点自证」三件套。** 在日志里直接读出模型被委托给了谁：

| 字段 | 含义 | 读法 |
|---|---|---|
| `req=` | **你要求的**后端 | 你自己的意图，不是事实 |
| `LANDED=` | **实际落在**哪个设备上 | **这才是事实** |
| `fallback=` | 如果没落在你要的地方，为什么 | 空 = 没发生回落 |

再加**张量指纹**做交叉印证：输出缓冲区的两个 L2 范数 —— `L2`（按**声明 dtype** 读）
与 `L2asFp16`（按 fp16 重读）。

> ⚠️ **指纹的正确读法（这里有两个常见误用，都是我自己踩过的）**
>
> **误用一：以为指纹是落点判据。** 不是。**落点判据是 `LANDED=` 字段**，
> 指纹只是**抓 dtype 错标的报警器**。
>
> **误用二：以为「NPU 行 `L2asFp16` 非零、CPU 行为 0」。** 这条早期假设**已被真机证伪**。
> 实测三个模型的输出**都声明为 FP32**，把 FP32 缓冲区按 fp16 重读必然得到垃圾 ——
> **CPU 行也不例外**。实测三元组（生产档 `det=cpu / rec=nnrt / cls=cpu`）：
>
> | 角色 | 落点 | `L2` | `L2asFp16` |
> |---|---|---|---|
> | det | `cpu` | 1076.7692 | **nan** |
> | rec | `NNRT:NPU_ohos.boot.hardware.kirin8020_v2_0` | **4.0489** | 3692.1536 |
> | cls | `cpu` | 0.9998 | **10424.0000** |
>
> **可比的是 `L2`**（rec 的 78 类 logits ≈ 4.05、cls 的三类概率 ≈ 1.0，都物理合理）。
> `L2asFp16` 只在**声明 fp16 却按 fp32 读**的错标场景里才有意义。

**为什么这样反而更强**：利用率回答「用了多少」，落点回答「**用没用、用在哪**」。
后者**可证伪**——日志里有确切的设备名字符串，任何人拿到日志都能复核。

### 可复现的最小验证

```bash
# 一条命令：把落点三件套与指纹从原始日志里全部抠出来
grep -hE "LANDED=" evidence/*.log | head -3
```

真实输出（**原文抄录**，未改一个字符）：

```
MATRIX y5fu_320x_head_fp32.ms cpu_t4 LANDED=CPU:t4 engine=ms req=cpu_t4 fallback= \
  in=[1,320,320,3]/NHWC p50=7.6664ms mean=8.1087ms p50Io=8.0116ms \
  L2=1042.6634 L2asFp16=0.0000 maxAbs=18.0232 dtype=43 verdict=PASS
```

四个字段各自独立可读：`req=cpu_t4`（我要求 CPU 4 线程）→ `LANDED=CPU:t4`（确实落在那里）
→ `fallback=`（空，没有回落）→ `verdict=PASS`。

想验证「落点确实会变」，把 `req` 换成 NPU 再跑一次，观察 `LANDED=` 是否变成
`NNRT:NPU_ohos.boot.hardware.kirin8020_v2_0`。

> **硬约束（已写进 `AGENTS.md` 与 ADR-0003）**：
> 论文、简历、演示中**禁止出现任何 NPU 利用率数字**。允许的表述只有
> **落点**、**延迟差**、**张量指纹**三种。

---

## 坑 2 · INT8 用了等于没用：`FULL_QUANT` 会整图静默回退 CPU

### 现象

> 📌 **本条的实测数据来自前期工作 `ShusenPaper`，不是本工程测的。**
> 按 `evidence-index.md` 第 6 节的规范，**必须显式标注、不得与新增重复计数**。
> 原始出处见 `ShusenPaper/results/`（已填写的华为提单包）。

你把模型转成 INT8，满心期待加速，结果**一点没快** —— 甚至更慢：

- 5 个模型（MobileNetV2/V3-Small、ResNet18/50、YOLOv8n）**全部**转成 `FULL_QUANT` INT8。
- 在 NPU 上构建时**失败**，返回 `ret=-1`，**没有任何错误详情**。
- 框架**不报错**，**静默回退到 CPU** 继续跑完。
- 结果是「INT8 在 NPU 上加速比 **1.00×**」，而回退路径甚至比纯 CPU 套件**慢 4~8%**。

**最坑的地方**：如果不看落点日志，你只会觉得「INT8 好像没啥用」，
**完全不会想到是「根本没上 NPU」**。

### 根因

**阻塞点被精确定位到「激活量化引入的 Quant / Dequant 节点」。**

三重证据（每模型 warm-up 10 + 正式 100 次，共 **5 轮**重复）：

1. **落点**：NPU 设备构建失败后，实际运行设备为 CPU。
2. **耗时**：「NPU 套件」与纯 CPU 套件 100 次推理耗时差 **< 0.2%** —— 如果真上了 NPU，
   不可能几乎一模一样。
3. **数值**：两侧输出校验和**逐位一致**（相对误差 **0.000%**）。

**对照实验把因果钉死了**：换用 `WEIGHT_QUANT`（**仅权重 INT8、激活保持浮点、无独立量化节点**）
的 3 个模型，在**相同协议**下可以正常委托 NPU：

| 模型 | `WEIGHT_QUANT` 加速 | vs CPU |
|---|---|---|
| MobileNetV2 | 2.16× | 2.76 ms |
| ResNet18 | ~10.8× | 2.98 ms |
| ResNet50 | ~12× | 6.22 ms |

校验和误差 0.08–0.25%。⇒ **问题不在 INT8 本身，在 `FULL_QUANT` 引入的
激活 Quant/Dequant 节点不被 NNRT 接受。**

> 这个结论和**坑 3 的「融合携带」模型完全互洽**：
> Quant/Dequant **没有融合邻居**，孤立出现 ⇒ 没有子图可以委托 ⇒ 整图回落。
> 两条坑其实是同一个结构性原因的两面。

### 正确做法

**在麒麟 8020 上，要 INT8 就用 `WEIGHT_QUANT`，不要用 `FULL_QUANT`。**

- `WEIGHT_QUANT` 是这台机器上**唯一可用的 INT8 形态**（权重 INT8 + 激活 FP16）。
- 如果你**必须**用 `FULL_QUANT`（比如精度需要），那就**必须接受它在 CPU 上跑**，
  并且**在落点日志里把它读出来**，不要自欺。
- **无论用哪种，都要检查 `LANDED=`** —— 这正是坑 1 那套方法存在的意义：
  它能让你在「感觉没变快」之前就发现「根本没上 NPU」。

> **边界**：`FULL_QUANT` 的精度问题另有一条 —— 合成均匀校准数据对残差网络分布不匹配，
> ResNet18/50 的 PTQ 精度会崩盘（78.8% / 85.7%），换高斯校准**也没修好**
> （怀疑是 converter 级的 `bias_correction` / 残差结构问题）。
> **所以那不只是「慢」，是「又慢又错」。**

### 可复现的最小验证

```bash
# 对同一份模型，分别用 FULL_QUANT 与 WEIGHT_QUANT 转，然后比对落点
# 期望：FULL_QUANT → LANDED=CPU；WEIGHT_QUANT → LANDED=NNRT:NPU_...
grep -hE "LANDED=" evidence/*int8*.log evidence/*wq*.log 2>/dev/null
```

**判据（三个一起看，缺一不可）**：

1. `LANDED=` 是不是 `NNRT:NPU_...`；
2. 「NPU 套件」与纯 CPU 套件的耗时差 —— **< 1% 就说明没真上 NPU**；
3. 两侧输出校验和 —— **逐位一致 = 走了同一条计算路径**。

---

## 坑 3 · 同一个算子，一边能跑一边不能：支持性是「模型 × 工具链」的联合属性

### 现象

同一个算子，在一条工具链上被拒、在另一条上完好；甚至**同一份 ONNX，一侧连模型都产不出来**。

实测：36 个算子里 **20 个可独立编译、16 个被 NNRT 拒收**（`ret=-1`，无详情）——
被拒的包括 `relu` / `sigmoid` / `softmax` / `maxpool` / `pad` / `cast_f16` / `transpose` / `resize` / `tanh`。
这些**看起来最普通的算子**居然上不去 NPU，非常反直觉。

### 根因

**「NPU 支持性」不是硬件属性，是 `模型 × 工具链` 的联合属性。** 三层机制：

**第一层 · 两条工具链的算子覆盖不同。**
MindSpore Lite 官方算子表 198 个算子里只有 **58 个**有 Kirin NPU 实现，
且**全部 FP16-only**（`LayerNormFusion` / `EmbeddingLookupFusion` / `Erf` / `RealDiv` / `Shape` 完全没有）；
而 CANN 侧有 **166 个 IR 算子**。

**第二层 · 「独立委托 vs 融合携带」——这是解释力的核心。**
被拒的算子**如果孤立出现**，NNRT 只看到它自己 ⇒ 无子图可委托 ⇒ **必切子图回落 CPU**。
但如果它**做 Conv 的融合邻居**，就会被一起带上 NPU。

> ⚠️ **边界**：这个模型目前是**相关性**证据（ResNet 内含被拒算子却整体加速 + 分区日志 `NPU:2,CPU:1`），
> **尚未做因果证明**。要做成因果，需要**同权重、逐算子插桩**的对照实验。
> 引用时**不能说成已证因果**。

**第三层 · 校验方式不同也会给出不同答案。**
`.om`（CANN）侧的探针是**单算子独立编译**，`.ms`（NNRT）侧是从**整模型**里判定的。
所以两侧的数字**不能直接比**。

### 正确做法

**实测证据：把 51 个算子探针从 ONNX 转成 CANN `.om`，真机上逐个跑三关，`51/51` 全部通过。**

```
compat=0 : 51      construct=ok : 51
build_rc=0 : 51    run_rc=0 : 51
```

**零失败、零回落** —— 包括 `.ms`/NNRT 侧被拒的那一批
（`relu` · `sigmoid` · `softmax` · `maxpool` · `pad` · `cast_f16` · `transpose` · `resize` · `tanh`）。

最尖锐的一例是 **`convtranspose`**：它在 `.ms` 侧**根本转不出来**
（`converter_lite 2.6.0` 形状推断失败），CANN 侧却**转换成功并跑通**。
同一算子、同一份 ONNX，一侧连模型都产不出来，另一侧能跑。

**可操作的三条结论**：

1. **模型上不去 NPU 时，先别改模型** —— 先换工具链试。
   两条链的算子集不同，很可能换一条就过了。
2. **看算子时不能只看「它本身支不支持」**，要看**它在图中是否孤立**。
   把它挪到 Conv 旁边（或反过来拆开），落点可能就变了。
3. **两侧的数字不能直接比**（校验方式不同）。要比就**同链内比**。

> ⚠️ **两条必须一起说的边界**：
> - `51/51 全通过` **只证明准入边界，不证明 CANN 更快**。生产档实测仍是 MS Lite
>   在识别器上更快（rec **3.99 ms** vs CANN 的 **5.19 ms**）。
> - `.om` 侧那批数据**仅 3 次、无热身、无热态标注 ⇒ 延迟只可排序，不可引用**。
> - **不许写「CANN 全通过 ⇒ CANN 更快」** —— 这是 `evidence-index.md` 明列的禁止项。

### 可复现的最小验证

```bash
# 逐算子三关结果（51 行）+ 真机原始回传
head -5 models_om_ops/op_collide.csv
# 期望看到每个算子四列：hiai_compat_code / construct+build_rc / run_rc / 延迟
```

判据：`compat=0` 且 `build_rc=0` 且 `run_rc=0` 才算通过。
**任一关失败都要记录具体原因**，并区分「格式不对」与「算子不支持」——**不得静默跳过**。
（这条是本票验收标准里明写的，因为静默跳过正是最容易骗到自己的失败模式。）

---

## 坑 4 · GPU 推理：不是方法没找对，是官方没提供这条路

### 现象

看到 `req=gpu` 之后落点是 `LANDED=CPU, fallback=GPU:fp16(fail)`，你会很自然地想：
「是不是我 GPU 参数没配对？换个 precision mode 试试？」

实测三个模型在 Vulkan 上都**比 CPU 慢**（小图提交开销主导）。
如果就此写成「GPU 比 CPU 慢 2–5 倍」，那是个**站不住的结论** ——
它会被反问「你确定你用对了 GPU 的调用方式？」

### 根因

**去查一手资料之后得到的结论是：官方确实没有提供这条路。**
（这一节的**全部**依据都在 `docs/notes/gpu-official-verdict.md`，下面每条都可回溯。）

**一、官方 AI 推理栈的计算单元清单里，GPU 那一格是空的。**

| Kit | 官方原文里的计算单元 |
|---|---|
| **CANN Kit** | 「协同调度设备的 **NPU、CPU** 等硬件资源」；「异构计算…使用到的计算单元类别包括 **CPU、NPU** 等」——**全篇无 GPU** |
| **NNRt Kit** | 「NNRt 强依赖硬件，只适用于支持 **NPU** 的设备」 |
| **MindSpore Lite（端侧）** | 官方支持列表只有「通用 **CPU** 与 **Kirin NPU**」 |

⇒ **麒麟上的官方定位是：GPU 管渲染，NPU 管推理。**

**二、官方确实有 GPU 计算能力，但全在图形 Kit 里，定位是渲染，不是通用 compute。**

- **XEngine Kit**（Maleoon GPU 驱动框架）：Subpass Shading、GPU 基数排序、光追。C API `HMS_XEG_*`。
- **Graphics Accelerate Kit**：官方明确「**不做渲染绘制**，对已有渲染做加速、功耗优化」。
- **原生 Vulkan**：SDK 内置 `libvulkan.so`，有官方开发文档。
- ⇒ **没有官方的通用 GPU compute / OpenCL 封装**（OpenCL 在 Android 7+ 已被禁）。

**三、MindSpore Lite 的 GPU 回落是平台设计，不是你的配置问题。**
官方构建文档原文：

> `MSLITE_GPU_BACKEND`「**only opencl is valid when the target OS is not OpenHarmony**」，
> 并明确「**目前 OpenHarmony 系统仅支持 CPU 推理，不支持 GPU 推理**」。

三条佐证：端侧 GPU 包只出 **Android-aarch64**（HarmonyOS 只有 CPU/NPU）；
GPU delegate 的支持设备只列 OpenCL（ARM Mali / Adreno）、CUDA、TensorRT，**Maleoon 不在其中**；
`GPUDeviceInfo` 虽有 `SetPrecisionMode` / `SetEnableFP16`，但 OpenHarmony 上**没有 GPU 后端**，
**设了也无效** —— 这正是你看到 `fallback=GPU:fp16(fail)` 的原因。

**四、ncnn 官方自己就说过这件事。** ncnn FAQ 原文（`gpu-official-verdict.md` 第四节）：

> *"It is common that your model runs slower on gpu than cpu on arm devices like mobile phones,
> since we have quite good arm optimization in ncnn"*

### 正确做法

**把 GPU 那一格从「我们测出来慢」升级为「有官方出处的、可辩护的否定结论」。**

- **口径**：只写「**通路成立且数值保真**」，**禁止写「GPU 加速 N 倍」** —— 这是
  `evidence-index.md` 明列的禁止项，因为它必须能被验证，而 GPU 加速在这台机器上做不到。
- **不要继续调 GPU 参数**。`fallback=GPU:fp16(fail)` 不是配置错误，
  是**平台没有这个后端**。继续试 `origin` / `fp16` 不会有结果。
- **想在 GPGPU 上做推理，就得换平台**。这不是本项目能解决的问题。

> **这一条对本项目的最大价值是方法学的**：
> 用户当时的批评是「我们真正去搜资料很少，都是自己在埋头苦干，这是非常不好的做法」。
> 结论从「实测慢」变成「官方文档层面的不支持」，靠的**不是更多实验，是查一手资料**。
> **埋头苦干能测出「慢」，查一手资料才能说清「为什么慢、是不是必然慢」。**

### 可复现的最小验证

```bash
# 1. 观察回落：期望 fallback=GPU:fp16(fail)，且 LANDED=CPU
grep -hE "req=gpu" evidence/*.log | head -3

# 2. 三条官方出处（2026-09-22 核实，原文见 docs/notes/gpu-official-verdict.md）
#    CANN Kit 介绍：       developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-introduction
#    NNRt Kit 概览：       developer.huawei.com/consumer/cn/sdk/neural-network-runtime-kit
#    MindSpore Lite 构建： mindspore.cn/lite/docs/en/r2.9.0/use/build.html
```

**判据**：如果在上面三条官方文档里**找不到**「OpenHarmony 支持 GPU 推理」的说法，
那本条的结论就成立。**结论的依据是官方文档的沉默，必须把出处列出来，不能只说「我们没找到」。**

---

## 坑 5 · 隔离基准 7.4 ms，装进流水线变 19.5–31.6 ms：测的是两个东西

### 现象

你在一个干净的基准里测出某个算子/模型只要 **7.4 ms**，
高兴地算出「那能做到 135 fps」。装进真实流水线一跑 —— **19.5–31.6 ms**，
慢了大约 **2 倍**。你会以为是自己代码写错了。

**这两个数都不是错的，它们测的不是一回事。**

### 根因

**隔离基准测的是「服务时间」，流水线内测的是「在资源竞争下的实际耗时」。** 三层原因：

**一、算术用错了量（最容易犯）。** `1000 / p50(frameMs)` 是**服务时间的倒数**，
**不是 fps**。本项目 `CONTEXT.md` 把「服务时间 / 到达率 / 完成率」定义为**三个不同的量**，
**只有后两者可以对外称 fps**。

**二、分桶混了。** `record()` 把**所有帧**塞进同一个滑窗取 p50，
但**检出帧要额外多跑矫正 + 识别 + CTC + 判色**。混桶得到的是**两种分布的混合物**：

| 档位 | 未检出（count=0） | 检出（count>0） |
|---|---|---|
| 生产档 infer p50 | **20.30 ms**（n=92） | **30.32 ms**（n=21） |
| 全 NPU infer p50 | **13.64 ms**（n=27） | 33.14 ms（n=1，样本不足） |

**「13 ms」与「20–25 ms」的差别不是抖动，是条件不同** ——
前者 ≈ 全 NPU + 未检出，后者 ≈ 生产档 + 未检出。

**三、真实瓶颈可能根本不在你优化的那段。**
生产档在**有车牌**时 frame p50 = **40.0 ms > 33.3 ms 预算**（余量 **−6.7 ms**），
所以到不了 30 fps。而**吃预算的是 CPU 上的检测段（19.61 ms，占 49.0%），
不是 NPU 上的识别段（3.98 ms，占 10.0%）**。

⇒ **「榨干 NPU」在这条流水线上已经不是瓶颈了 —— 继续压 NPU 收益极小。**
如果你只盯着 NPU 段的隔离基准数字，会一直优化错的地方。

### 正确做法

**四条纪律**：

1. **永远区分「服务时间」与「帧率」**。要报 fps 就用 `arrive` / `done` 这种**到达率/完成率**，
   不要用 `1000/p50` 倒推。
2. **永远分桶**。`hit_n` / `empty_n` 与 `rt_hit_p50` / `rt_empty_p50` **分开报**；
   `frameMs` 不分桶（吞吐关心的是每帧实际墙钟）。
3. **报隔离基准时必须标注「隔离」**，并**同时给出流水线内数字**。
   `evidence-index.md` 第 4.6 行就是把两个数并排写（**7.4 ms vs 19.5–31.6 ms，约 2×**）。
4. **先量预算分解，再决定优化什么**。用「余量 = 预算 − 实际」这个量，
   而不是「我还差多少倍」。

**另外，「帧率天花板」这个结论本身也翻过案，值得记下**：
早期结论说相机上限 ~30 fps、「40–50 帧不可达」。后来换 `NORMAL_VIDEO` 会话
+ 一条固定 `60-60` 的 `VideoOutput`，实测 **49.98 fps**（42.74–57.94，n=43）。
**「40–50 帧不可达」在流水线意义上仍成立**（有车牌时全 NPU 约 **43.55** fps），
但**理由要换**：从「**相机给不了**」改成「**流水线吃不下、并把相机背压回来**」。
⇒ **同一个结论，理由错了也要改；否则你会在错的地方努力。**

### 可复现的最小验证

```bash
# 隔离基准 vs 流水线内，同模型同后端同线程数
grep -hE "GAP" evidence/camera_gap_sweep.log | head -6
# 期望：能看到隔离 7.4 ms 与流水线内 19.5–31.6 ms 并排
```

**判据**：如果你在流水线里测到的数字**明显大于**隔离基准，
**先检查分桶和资源竞争**，不要急着怀疑自己的实现。

---

## 五条坑的一张总表

| # | 坑 | 一句话 | 判据字段/命令 | 数据来源 |
|---|---|---|---|---|
| 1 | 利用率读不到 | 改用落点自证 | `LANDED=` / `fallback=` / `L2` | 本工程 |
| 2 | `FULL_QUANT` 静默回退 | 要 INT8 就用 `WEIGHT_QUANT` | `LANDED=CPU` + 耗时差 <1% + 校验和逐位一致 | **前期工作** |
| 3 | 支持性是联合属性 | 上不去先换工具链 | `op_collide.csv` 三关 | 本工程 |
| 4 | GPU 无官方通路 | 别调参数，查文档 | 官方三条出处 | **官方文档** |
| 5 | 隔离基准 ≠ 流水线内 | 分桶 + 报余量 | 7.4 ms vs 19.5–31.6 ms | 本工程 |

> ⚠️ **计数提醒**：坑 2 的量级数字（`2.76/2.98/6.22 ms`、`2.16×/~10.8×/~12×`）
> 是 **`ShusenPaper` 前期工作**的，**不要**算进本工程的新增结论。
> 本文引用它只是为了让「`WEIGHT_QUANT` 能留 NPU」这条**有对照可依**。

---

## 上游参考

- 构建与环境类四个坑：[`npu-pitfalls-build-and-env.md`](npu-pitfalls-build-and-env.md)
- 证据标准（落点/延迟差/指纹的来龙去脉，含「利用率不可测」的完整依据表）：
  [`docs/adr/0003`](../adr/0003-evidence-standard-latency-delta-and-landing.md)
- 论文主张与算子覆盖边界：[`docs/adr/0002`](../adr/0002-thesis-landing-evidence-and-operator-coverage.md)
- GPU 官方结论全文（一手资料逐条核实）：[`docs/notes/gpu-official-verdict.md`](../notes/gpu-official-verdict.md)
- 算子对撞实测：[`docs/notes/t8-operator-collision.md`](../notes/t8-operator-collision.md)
- 相机路预算分解：[`docs/notes/camera-npu-headroom.md`](../notes/camera-npu-headroom.md)
- 60fps 吞吐实验：[`docs/notes/t9-60fps-inference-throughput.md`](../notes/t9-60fps-inference-throughput.md)
- **全部数字的单一事实源**：[`docs/evidence-index.md`](../evidence-index.md)

> **维护提示**：本文引用的每一个数字都必须在 `evidence-index.md` 里能查到。
> 改了数字请**先改 index，再改本文** —— 顺序反了就会出现两处不一致，
> 而 `tools/verify_published_numbers.py` 只守 index，**守不到本文**。
