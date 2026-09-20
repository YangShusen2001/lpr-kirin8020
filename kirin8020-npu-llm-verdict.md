# Kirin 8020 (HUAWEI nova 14 Pro, MIA-AL00, HarmonyOS 6.1 / API 24) — can it run an LLM on the NPU?

**Verdict: NO — not on the NPU, via any officially supported path.** The block is not "untested hardware"; it is an explicit, machine-readable device gate published by Huawei.

Method note: `web_search` was unavailable this session (HTTP 402, insufficient balance). All Huawei findings below come from the official doc API (`getDocumentById` / `getCatalogTree`) and are quoted verbatim. External claims are marked as such.

---

## (A) CANN LLM Engine — verdict for Kirin 8020: **HARD NO**

### What it is
| Field | Value |
|---|---|
| Product name | **CANN LM Engine** (a.k.a. CANN LLM Engine); "LLM Engine是其在大语言模型场景下的具体应用" |
| Kit | **CANN Kit** (CANN异构计算框架服务) |
| Header / lib | `<CANNKit/llm_engine.h>` / `libcann_llm_engine.so` |
| SysCap | `SystemCapability.AI.CANN.LLMEngine` |
| Start version | **6.1.1(24)** |
| API surface | 31 symbols: `HMS_LLMEngineExecutor_CreateFromExecutorJson`, `HMS_LLMEngineExecutor_Generate` / `GenerateAsync`, `HMS_LLMEnginePrompt_SetText` / `SetTokenId`, `HMS_LLMEngineContext_SetOnOneTokenGenerateDoneFunc`, `..._GetPrefillTimeMs` / `GetDecodeTimeMs`, `HMS_LLMEngine_InferPerfMode`, … |

Docs: `https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-llm-developer` (overview), `.../cannkit-llm-summary` (hardware+models), API ref `.../harmonyos-references/cannkit-llm-engine` (`llm_engine.h`).

### Exact supported-hardware quote
From `cannkit-llm-summary` (「模型要求」/「硬件要求」):

> **模型要求** 当前版本支持Qwen2.5-1.5B、DeepSeek-R1-Distill-Qwen-1.5B、Glm-1.5b、Qwen2.5-7B-Instruct、Qwen3-8B模型。
> **硬件要求** kirin X90平台。

From `cannkit-llm-usage-environmental-preparation`:

> **支持平台：Kirin X90（支持以下所有模型）。**

### Is "kirin X90" a hard gate? **Yes — and there is a second, even harder gate.**

**Gate 1 — SoC.** Kirin X90 is a distinct series, not an umbrella for all Kirin. Evidence:
- Platform plugin packages shipped in 开发准备 are exactly three: **`kirin9020`, `kirinx90`, `kirin9030`**. There is **no `kirin8020`**.
- `cannkit-basic-architecture`: "**Kirin9020/Kirin9030/KirinX90系列处理器：耦合架构**" — three named series.
- `cannkit-large-language-one-stop` config: `quant_param_2` — "True：**Kirin9020** / False：**KirinX90**" (treats them as different targets).
- `cannkit-ascend-kirin-map`: Ascend910B/910C ↔ **KirinX90、Kirin9030** (8020 absent).

**Gate 2 — device type (decisive).** In the API reference metadata, **all 31 `HMS_LLMEngine_*` symbols carry `deviceType":"0100000"` and `deviceVersion":"2in1 6.1.1(24)"`.** Decoding the 7-bit mask against Huawei's own pairs (`1111000` = "phone,2in1,tablet,tv"; `1111010` = phone,2in1,tablet,tv,wearable):

```
0100000  ->  [0]phone [1]2in1 [0]tablet [0]tv [0] [0]wearable   ==  2in1 ONLY
```

CANN LLM Engine is **PC/2in1-only**. It is not merely gated away from Kirin 8020 — it is not offered on **any** phone, X90 included. By contrast, the classic CANN `HiAI_*` inference APIs carry `deviceType":"1111000"` (134 anchors → phone, 2in1, tablet, TV), which is how the bitmask decode is validated.

**Answer to "any statement that non-X90 Kirin SoCs cannot use it?"** There is no sentence saying "Kirin 8020 is unsupported." But the API reference `deviceType`/`deviceVersion` metadata **is** the device allowlist, and it excludes phones entirely; the platform-plugin list excludes 8020; the stated hardware requirement is Kirin X90. Three independent gates. Verdict: **not available on Kirin 8020, and not obtainable by any workaround.**

---

## (B) Any LLM on a Kirin NPU? — **No reproducible evidence found**

Blunt answer: I found **zero** credible, reproducible report of a transformer LLM executing on a Kirin NPU inside a HarmonyOS app. Caveat: `web_search` was down, so my community sweep is weaker than it should be; this is absence of evidence gathered through direct fetches, not a proven universal negative.

What the direct evidence shows:

1. **`SKL-666666/mnn-local-ai-chat` is CPU, not NPU.** Its own `docs/GGUF推理与MNN推理对比报告.md` states plainly:
   > **llama.cpp（本项目配置）：纯 CPU 推理（OpenMP 关闭 → 单线程）**
   
   The 4→40 tok/s gain comes from `-DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod` (udot/sdot) — ARM **CPU** dot-product instructions. The repo never claims NPU inference.

2. **MNN's Huawei-NPU backend cannot run LLMs.** MNN's own README backend matrix:
   ```
   | NPU | CoreML | A | C | C | C |
   |     | HIAI   | A | C | C | C |     <- Normal / FP16 / BF16 / Int8
   ```
   `HIAI` (Huawei NPU) is **`A` for FP32 but `C` (Not Support) for FP16 and Int8.** LLMs in practice require int8/int4 weights and fp16 activations. A backend that supports neither is not an LLM backend. (`source/backend/hiai/` links `libhiai.so`, `libhiai_ir.so`, `libhiai_ir_build.so`.)

3. **NNRt is not a path.** Official `neural-network-runtime-kit-introduction`:
   > **NNRt目前支持常用算子56个** … **NNRt目前仅支持同步推理** … **NNRt仅可提供已在底层接入的AI加速硬件的AI推理能力，不提供CPU等通用硬件上的AI推理能力。**

   (Note: this corrects the background's "does NOT expose CPU or GPU as NNRt devices" — the doc says it doesn't provide CPU *inference capability*; CANN Kit itself does support CPU fallback via 异构.)

The common "LLM on Kirin" reports are **ARM CPU with dotprod** (MNN / llama.cpp / MindSpore Lite CPU backend), routinely mislabelled as NPU.

---

## (C) What the Kirin NPU *can* realistically host

**CANN Kit (HiAI Foundation) with `.om` offline models IS available on Kirin 8020 phones.** From `cannkit-introduction`:

> **约束与限制** 本Kit仅适用于带有Kirin NPU的Phone、Tablet、PC/2in1、TV设备。

So the `.om`/OMG toolchain — not the LLM Engine — is the realistic NPU surface. Supported IR operators: **166** (`cannkit-supported-operators`): array_defs 36, math_defs 61, nn_defs 36, image_defs 29, detection_defs 2, const_defs 2.

Model Zoo (`cannkit-model-zoo`) is **100% CNNs**, with per-model ms measured on a **kirin 9000** phone: Resnet18 2.63 ms, Mobilenet_v1 2.16 ms, Resnet50 5.15 ms, Yolo_v5 4.74 ms, DeepLab_v3 17.40 ms, VGG16 16.56 ms, FCN 131.23 ms.

**Largest realistic model class: CNNs — ResNet-50 / YOLOv5 / DeepLabv3 scale.** Vision encoders up to ~100M params are plausible (ResNet-50 ≈ 25M, VGG16 ≈ 138M already ships). Small transformers are *theoretically* reachable — the op list does contain `MatMul`, `BatchMatMul`, `GemmD`, `QuantizedMatMul`, `LayerNorm`, `Softmax` — but there is **no** FlashAttention, RoPE, KV-cache, or dynamic-shape autoregressive decode support documented, and the one official transformer path (LLM Engine) is 2in1-only. Treat autoregressive transformer decode as **unsupported in practice**.

---

## (D) System-level on-device LLM for third-party apps: **not on this device**

| Capability | Kit | Device gate | Verdict for nova 14 Pro |
|---|---|---|---|
| `localChatModel` (Qwen25-7B-Instruct, Matrix model lib) | Data Augmentation Kit | `deviceType 0100000` → **2in1 only**; doc: "当前端侧模型问答**仅支持PC/2in1设备类型**"; "**仅对企业开发者**提供申请能力" | ❌ No |
| Intents Kit (小艺对话/搜索/建议) | Intents Kit | Phone/Tablet/2in1, HarmonyOS 5.0+, **enterprise developers only**, China only | ⚠️ Not an LLM API — it distributes *intents*; the LLM stays inside the system |
| 端侧A2A / Agent Framework (HMAF) | Agent Framework Kit | API 24+, agent-to-agent protocol | ⚠️ Agent transport; agent *client* is a system app |

**There is no `@hms.ai.*` generative-LLM API.** The only `hms.ai.*` APIs are `textToSpeech` and `speechRecognizer` (Core Speech Kit / Speech Kit) — TTS and ASR, not generation. **Third-party apps cannot call HarmonyOS's system LLM.**

---

## (E) Credible on-device path: **CPU + dotprod**

Repo: `https://github.com/SKL-666666/mnn-local-ai-chat` — "HarmonyOS 本地 AI 对话应用：MNN + llama.cpp 双引擎", Apache-2.0, C++, created 2026-08-10, pushed 2026-08-14, **2 stars, 0 forks, 1 open issue**.

Claimed numbers (from its README/CHANGELOG v1.2.0):
- llama.cpp recompiled `-DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod` → **量化推理 4 → 40 tok/s (10×)**; "HAP 内 `libllamallm.so` 含 1036 条 `udot/sdot` 指令（旧版 0 条）"
- Modes: performance 8/8 threads, balanced 4/6, power-save 1/2 + 2048-token cap
- `n_batch 4096 / n_ubatch 2048`; KV prefix reuse; context 4096 → 6144
- Thermal guard: ≥45 °C blocks chat, ≥43 °C downshifts

**Honest reading:** this is **pure CPU dotprod** (the repo's own doc says so). "40 tok/s" is a best case, near-certainly a 0.5B-class model in performance mode. It is a 2-star hobby repo with no independent reproduction — treat 40 tok/s as *indicative, unverified*, not a benchmark. What is genuinely verified: dotprod gives a real ~10× over a non-dotprod build, and MNN/llama.cpp run on ARM CPU on HarmonyOS.

---

## (F) Model size vs RAM — explicit arithmetic

**Huawei publishes no RAM figure for nova 14 Pro.** The official specs page (`consumer.huawei.com/cn/phones/nova14-pro/specs/`) lists only 机身内存 256 GB / 512 GB / 1 TB **ROM** — no 运行内存 row. The vmall product attribute dump likewise has no 运行内存 field. Third-party sources (Baidu Baike, Zhihu) returned HTTP 403. **12 GB is the widely-reported figure but I could not confirm it from a primary source — verify on-device before committing.**

Q4_K_M ≈ 0.55–0.6 bytes/param; add KV cache + runtime overhead.

| Model | Q4 weights | +KV/overhead | Fits in ~4–6 GB app budget? |
|---|---|---|---|
| 0.5B | ~0.35 GB | ~0.5 GB | ✅ comfortable |
| 1.5B | ~1.0 GB | ~1.4 GB | ✅ comfortable |
| 3B | ~1.9 GB | ~2.5 GB | ✅ fine |
| 7B | ~4.4 GB | ~5.5–6 GB | ⚠️ marginal — OOM risk |

If the device is **12 GB**: HarmonyOS + services typically leave roughly 4–6 GB usable for an app, so 0.5B/1.5B/3B are safe and 7B is tight. If it is **8 GB**: 7B is not advisable.

Corroborating signal: the MNN repo caps saved session data at 20 MB and truncates single messages at 512 KB specifically to stop "闪退后黑屏" from **JS heap OOM** — memory pressure on this class of device is real.

---

## Blunt recommendation

1. **Do not pursue NPU LLM on Kirin 8020.** CANN LLM Engine is 2in1-only *and* Kirin X90-only; there is no allowlist entry, no platform plugin, and no workaround. Even a Kirin X90 **phone** cannot use it.
2. **Do not pursue NNRt or MNN-HIAI for an LLM.** NNRt has 56 ops and is sync-only; MNN's HIAI backend is FP32-only (`C` for FP16/Int8), which disqualifies quantized transformers.
3. **Ship a CPU LLM.** MNN-LLM or llama.cpp with `-DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod`, Q4_K_M, **1.5B–3B** class. This is the only credible on-device generative path on this device. Expect single-digit-to-low-tens tok/s, not 40.
4. **Use the NPU for what it is good at:** `.om` CNNs via CANN Kit (image classification, detection, segmentation, super-resolution) — officially supported on Kirin NPU phones.
5. **For real LLM quality, call the cloud.** No system on-device LLM is exposed to third-party apps on this device, and the one Huawei ships (`localChatModel`) is PC-only and enterprise-gated.

### Primary URLs
- CANN LLM overview: https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-llm-developer
- CANN LLM hardware/models: https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-llm-summary
- CANN LLM env prep ("支持平台：Kirin X90"): https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-llm-usage-environmental-preparation
- `llm_engine.h` API ref: https://developer.huawei.com/consumer/cn/doc/harmonyos-references/cannkit-llm-engine
- CANN Kit intro (phone constraint): https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-introduction
- Dev prep (kirin9020/kirinx90/kirin9030 plugins): https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-preparations
- Supported operators (166): https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-supported-operators
- Model Zoo (CNNs): https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-model-zoo
- NNRt intro (56 ops, sync-only): https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/neural-network-runtime-kit-introduction
- Ascend↔Kirin map: https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-ascend-kirin-map
- localChatModel (2in1/enterprise): https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/dataaugmentation-localchatmodel
- Intents Kit: https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/intents-introduction
- nova 14 Pro specs (no RAM listed): https://consumer.huawei.com/cn/phones/nova14-pro/specs/
- MNN repo: https://github.com/SKL-666666/mnn-local-ai-chat
- MNN backend matrix: https://github.com/alibaba/MNN
