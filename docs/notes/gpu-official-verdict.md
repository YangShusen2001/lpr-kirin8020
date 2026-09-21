# GPU 在麒麟上做推理：官方结论（一手资料核实）

- **日期**：2026-09-22
- **起因**：用户不接受「GPU 比 CPU 慢 2–5 倍」这个实测结论，要求**重新去搜一手资料**，
  确认到底有没有官方的、正确的 GPU 调用方式。
  用户的批评原话：「我们真正去搜资料很少，都是自己在埋头苦干，这是非常不好的做法。」
- **结论**：**不是我们没找对方法，是官方没提供这条路。**
- **对论文的意义**：把 GPU 那一格从「我们测出来慢」升级为
  **「有官方出处的、可辩护的否定结论」**。

> 本文与 `docs/spec.md` 的「Out of Scope · GPU 加速叙事」一节互证。
> 那一节说「不许写 GPU 加速」，本文给出**为什么**（官方文档层面的原因）。

---

## 一句话结论

**麒麟平台上的官方定位是：GPU 管渲染，NPU 管推理。**
华为官方 AI 推理栈（CANN Kit / NNRt Kit / MindSpore Lite）的计算单元清单里，
**GPU 那一格是空的**。

---

## 一、官方 AI 推理栈里没有 GPU

| Kit | 官方原文里的计算单元 | 来源 |
|---|---|---|
| **CANN Kit** | 「协同调度设备的 **NPU、CPU** 等硬件资源」；基本概念章节「异构计算…使用到的计算单元类别包括 **CPU、NPU** 等」——**全篇无 GPU** | [官方] `developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-introduction` |
| **NNRt Kit** | 「NNRt 强依赖硬件，只适用于支持 **NPU** 的设备」 | [官方] `developer.huawei.com/consumer/cn/sdk/neural-network-runtime-kit` |
| **MindSpore Lite（端侧）** | 官方支持列表只有「通用 **CPU** 与 **Kirin NPU**」 | [官方] `mindspore.cn/lite/docs/zh-CN/r2.9.0/use/downloads.html` |

**官方确实有 GPU 计算能力，但全部落在图形 Kit 里，定位是渲染：**

- **XEngine Kit**（Maleoon GPU 驱动框架）：Subpass Shading 支持在 Subpass 内用 **Compute Shader**；
  HPS 提供 GPU 基数排序（6.0.0(20)+）；光追。C API `HMS_XEG_*`。[官方]
- **Graphics Accelerate Kit**：官方明确「**不做渲染绘制**，对已有渲染做加速、功耗优化」。[官方]
- **原生 Vulkan**：SDK 内置 `libvulkan.so`，官方有 Vulkan Development 文档。[官方]

⇒ **没有官方的通用 GPU compute / OpenCL 封装**（OpenCL 在 Android 7+ 已被禁）。

---

## 二、MindSpore Lite 的 GPU 回落是平台设计，不是配置问题

这一条**直接解释了**我们实测到的 `req=gpu → LANDED=CPU, fallback=GPU:fp16(fail)`。

官方构建文档原文：

> `MSLITE_GPU_BACKEND`「**only opencl is valid when the target OS is not OpenHarmony**
> and -I arm64」；并明确「**目前 OpenHarmony 系统仅支持 CPU 推理，不支持 GPU 推理**」。

[官方] `mindspore.cn/lite/docs/en/r2.9.0/use/build.html`

三条佐证：

1. 下载页：端侧 GPU 包只出 **Android-aarch64**，HarmonyOS 端侧只有 CPU/NPU。[官方]
2. GPU delegate 的支持设备：源码/文档只列 OpenCL（ARM Mali / Adreno）、CUDA、TensorRT，
   **Maleoon 不在其中**。[源码/社区]
3. `GPUDeviceInfo` 确有 `SetDeviceID` / `SetPrecisionMode("origin"/"fp16")` / `SetEnableFP16`，
   但 OpenHarmony 上**没有 GPU 后端**，设了也无效。[官方]
4. 社区只有「NPU 算子回落 CPU」的讨论，**未见 GPU 成功案例**。[社区]

---

## 三、ncnn 官方自己就说：ARM 手机上 GPU 比 CPU 慢是常态

ncnn 官方 FAQ 原文：

> *"It is common that your model runs slower on gpu than cpu on arm devices like mobile
> phones, since we have quite good arm optimization in ncnn"*

并承认其 Vulkan 实现「far from the preferred state」，winograd / fusion / fp16 仍在计划中。
[官方仓库] `github.com/Tencent/ncnn/wiki/FAQ-ncnn-vulkan`

**两个 open 的实现级缺陷**（说明 ncnn-Vulkan 本身也还有余量，但那不是我们该修的）：

- **#6857**：staging 下载绕过 `HOST_CACHED`，仅 **0.33 GB/s（差 12.7 倍）**。[源码]
- **#6858**：**MatMul 没有 Vulkan 实现**，attention 类模型会中途回落 CPU。[源码]

⇒ **我们实测的 41–86.8 ms（Vulkan）vs 16.2–20.9 ms（CPU）完全在预期内，不是我们的 bug。**

---

## 四、唯一还没被排除的一条路

**HiAI Foundation**：官方博客称提供「高性能的 **NPU、CPU、GPU** 算子」异构平台。
但它的 DDK 公开支持列表是 **Kirin 820 / 985 / 990 / 9000**，**不含 8020**，
且在 HarmonyOS 6.1 / API 24 上是否仍开放**未证实**。[社区/官方博客]

> **登记为待验证项**，但优先级低于 NPU 相关的工作 —— 因为即使它开放，
> 它提供的仍是「另一条调用 NPU/GPU 的路」，不改变「GPU 不如 CPU」这个结论。

---

## 五、对论文与对外材料的写法

**可以写的**（有出处）：

> 官方 AI 推理栈（CANN / NNRt / MindSpore Lite）在 HarmonyOS 上的计算单元是
> **CPU 与 NPU**，不含 GPU；MindSpore Lite 的 GPU 后端在 OpenHarmony 上
> **未被编译进去**（官方构建文档明示），因此 `SetDevice(GPU)` 必然回落 CPU。
> ncnn-Vulkan 通路成立且数值保真（`vkLayers=218/218`、`match=1`），
> 但实测比 CPU 慢 2–5 倍，与 ncnn 官方 FAQ 的陈述一致。

**不能写的**：

- ❌「GPU 加速 N 倍」
- ❌「GPU 不可用」——通路是成立的，慢是另一回事
- ❌「我们没找到方法」——**官方没提供这条路，这是平台边界，不是我们的疏漏**

**新增的可写内容**（本次检索的产出）：

- ✅ 「GPU 计算能力存在，但全部在图形 Kit（XEngine Kit 的 Subpass Shading / Compute Shader、
  GPU 基数排序）里，官方定位是**渲染加速**，不是推理。」
- ✅ 「唯一可能被忽略的通路是 HiAI Foundation，但其 DDK 支持列表不含 8020。」

---

## 六、方法论教训（写进论文的 Discussion）

**这一节的起因是一次自我批评**：用户指出「我们真正去搜资料很少，都是自己在埋头苦干」。

一次针对性的官方资料检索，产出了：

1. 一个**比实测更强的结论**（从"我们测出来慢"到"官方没提供这条路"）
2. 一个**根因**（OpenHarmony 没编译 GPU 后端）
3. 一个**独立佐证**（ncnn 官方 FAQ）
4. 一条**还没被排除的路**（HiAI Foundation）

⇒ **"先搜一手资料"与"先动手实测"应该并行，而不是后者替代前者。**
实测能告诉你"现在是什么样"，一手资料能告诉你"为什么是这样、有没有别的路"。
两者缺一，结论都不完整。
