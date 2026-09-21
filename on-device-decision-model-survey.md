# Deployable decision model / small VLM for "read phone screen → decide → tap coordinate" on Kirin 8020 + HarmonyOS

Research note, 2026. Companion to [`harmonyos-npu-gpu-squeeze-research.md`](harmonyos-npu-gpu-squeeze-research.md)
(which established the HarmonyOS NPU access paths from primary sources) and
[`on-device-chinese-lpr-survey.md`](on-device-chinese-lpr-survey.md).

**Given, not re-verified:** "Jev" (TypeSafe AI) is API-only, text-only, no public weights, no vision,
not available in mainland China. It is out of scope.

**Verification tags** — `[V]` read in a primary source this session (HF API metadata / file tree, GitHub API,
Huawei doc API, MindSpore docs). `[T]` vendor or third-party claim, self-reported. `[?]` could not confirm.

**Method note.** The `web_search` / `web_fetch` tools were dead this session (HTTP 402 on the search
endpoint, `fetch failed` on fetch). Everything below was retrieved with `Invoke-WebRequest`/`Invoke-RestMethod`
against the HuggingFace JSON API (`/api/models/<id>`, `/api/models/<id>/tree/main?recursive=true`),
`raw.githubusercontent.com`, the GitHub REST API, `www.mindspore.cn`, and Huawei's `documentPortal` JSON API
(the technique documented in the companion NPU note). Sizes are **exact byte sums from the HF file tree**,
not estimates. `developer.huawei.com` HTML pages return an empty shell; the CANN facts below came through
`POST https://svc-drcn.developer.huawei.com/community/servlet/consumer/cn/documentPortal/getDocumentById`.

---

## 0. Headline answers

1. **No Jev-style reproduction is small enough to be comfortable on a mid-range Kirin NPU.** The smallest
   credible open "System One" decision models are ~264–270 MB encoders (`DavidHatley/system-one-mini`,
   `shreyanbr/system-one-distilled`) — but those are DeBERTa/DistilBERT *classifiers*, i.e. they are
   decision models in name only. The best-engineered one, **Laya, is 421M params / 803.6 MB and already has
   a working ONNX export** `[V]`.
2. **None of them can see the screen.** Every Jev reproduction found is **text-only** — same limitation as
   Jev itself. The single vision variant (`thaitea/laya-vision-smolvlm-256m`) exists but is
   **CC BY-NC-SA 4.0** (non-commercial) and experimental `[V]`.
3. **MindSpore Lite + NNRt cannot run a transformer on the Kirin NPU.** Not "is hard" — the operator table
   shows **LayerNorm and EmbeddingLookup have no Kirin NPU implementation at all**, and every NPU-supported
   op is **FP16-only** (no INT8 in the NPU column). This is a primary-source finding `[V]`.
4. **A transformer LLM *has* been run on a Kirin NPU on HarmonyOS** — but through **CANN Kit / LLM Engine**,
   not MindSpore Lite, and the concrete code I found is an unlicensed 0-star hobby repo `[V]`.
5. **Kirin 8020 has no published TOPS figure.** cpudb leaves it blank; the widely-copied "14.7 TOPS" belongs
   to the **Exynos 1580** column on the same comparison page `[V]`.
6. **Blunt: do not put a model on the NPU for this use case.** For "claim daily coins in a video app",
   the decision complexity is near zero. OCR/template matching on CPU + a deterministic state machine is
   the correct design.

---

## (A) Model table — Jev-style reproductions and small decision models

All sizes are the **sum of weight files** from the HF file tree `[V]`.

| Name | URL | Params | Weights on disk | License | Runtime | → ONNX / NPU? |
|---|---|---|---|---|---|---|
| **Laya** (best supported) | [convaiinnovations/laya](https://huggingface.co/convaiinnovations/laya) | **421M** (ModernBERT-large 395M + 2-layer head) | **803.6 MB** (`model.safetensors`, bf16) | **Apache-2.0** | PyTorch `transformers`; `pip install laya` | **Yes — already exported.** Non-autoregressive, single forward pass → fixed shapes, NPU-shaped. |
| Laya multilingual | [convaiinnovations/laya-multilingual](https://huggingface.co/convaiinnovations/laya-multilingual) | 322M (mmBERT-base) | 614.0 MB | Apache-2.0 | same | Yes |
| Laya typed-decisions | [convaiinnovations/laya-typed-decisions](https://huggingface.co/convaiinnovations/laya-typed-decisions) | 421M | 803.6 MB | Apache-2.0 | same | Yes |
| **Laya ONNX (community)** | [Mattepiu/laya-onnx](https://huggingface.co/Mattepiu/laya-onnx) | 421M | **int8: 554.2 MB** / fp32: 1607.2 MB / fp16: 803.1 MB | Apache-2.0 | `onnxruntime` | **Already ONNX.** README claims ~15 ms CPU inference `[T]`. |
| Laya ONNX fp16 | [sevenreasons/laya-onnx-fp16](https://huggingface.co/sevenreasons/laya-onnx-fp16) | 421M | 807.1 MB | Apache-2.0 | onnxruntime | Already ONNX |
| **Laya Vision** | [thaitea/laya-vision-smolvlm-256m](https://huggingface.co/thaitea/laya-vision-smolvlm-256m) | SmolVLM-256M + head (~150M trained) | **902.5 MB** | **CC BY-NC-SA 4.0** ⚠️ non-commercial | `laya.load_vlm` | Possible but no export exists; NC license kills commercial use |
| **NanoJev** | [C-Tianyu/NanoJev](https://huggingface.co/C-Tianyu/NanoJev) | 0.6B backbone + attention Choice head | **2274.6 MB** (`best.safetensors`, fp32) | **unclear** — HF has no `license` field; card says code is MIT, "Qwen base retains upstream license" | PyTorch + custom `DecisionPredictor`; needs `disable_native_triton` | Not realistic as-is — custom head + custom code, no export |
| OpenJev (framework, no weights) | [GitHub30/OpenJev](https://github.com/GitHub30/OpenJev) | — | — | MIT | wraps any HF instruct model | It's a harness, not a model. 0★ |
| **OpenJev (the real weights)** | [AlexWortega/openjev](https://huggingface.co/AlexWortega/openjev) | Qwen3.5-4B (8658 MB) / Qwen3.5-35B-A3B (66 GB) + 4 MB MLP heads | 8658 MB / 76 GB | MIT | PyTorch | No. Far too big. |
| OpenJev-0.6B (LoRA) | [IamBusy/OpenJev-0.6B](https://huggingface.co/IamBusy/OpenJev-0.6B) | LoRA r=8 on Qwen3-0.6B | **4.4 MB adapter** + 4 KB head (base not included) | Apache-2.0 | PEFT | Adapter only; needs the 0.6B base separately |
| **Bespoke Nimble** | [bespokelabs/Bespoke-Nimble-9B](https://huggingface.co/bespokelabs/Bespoke-Nimble-9B) · [GitHub](https://github.com/bespokelabsai/nimble) (857★) | LoRA on Qwen3.5-9B | **165.2 MB adapter** (base not included) | Apache-2.0 | PyTorch + **CUDA BF16 required** | No. 9B base is not mobile. |
| PlayJev | [MoeclubM/PlayJev](https://github.com/MoeclubM/PlayJev) | — | — | MIT | TypeScript web app | **Not a model.** It is a visual IDE/playground for the *Jev cloud API*. 4★ |
| systemone-lite | [dwidlee/systemone-lite-0.5b](https://huggingface.co/dwidlee/systemone-lite-0.5b) | Qwen2.5-0.5B | 942.3 MB | Apache-2.0 | PyTorch | Possible, no export |
| **system-one-distilled** (smallest real) | [shreyanbr/system-one-distilled](https://huggingface.co/shreyanbr/system-one-distilled) | DeBERTa-v3-xsmall (33-label zero-shot) | **270.2 MB** | Apache-2.0 | PyTorch / ONNX | Yes — DeBERTa exports cleanly |
| **system-one-mini** (smallest real) | [DavidHatley/system-one-mini](https://huggingface.co/DavidHatley/system-one-mini) | DistilBERT-base | **264.5 MB** | Apache-2.0 | PyTorch | Yes |
| open-jev-deberta-v3-large | [com-kotobalabs/open-jev-deberta-v3-large](https://huggingface.co/com-kotobalabs/open-jev-deberta-v3-large) | DeBERTa-v3-large | 1655.7 MB | Apache-2.0 | PyTorch | Yes but large |
| jev-schema-scorer | [mobarmg/jev-schema-scorer-deberta-v3-large](https://huggingface.co/mobarmg/jev-schema-scorer-deberta-v3-large) | DeBERTa-v3-large | ~1.6 GB | MIT | PyTorch | Yes but large |
| modernbert-ja-310m-jev | [argos1111/modernbert-ja-310m-jev](https://huggingface.co/argos1111/modernbert-ja-310m-jev) | ModernBERT-ja 310M | ~620 MB | CC-BY-SA-4.0 | PyTorch | Japanese only |
| JEV-CPU | [Meanblock/JEV-CPU](https://huggingface.co/Meanblock/JEV-CPU) | Qwen3-0.6B | ~1.2 GB | MIT | PyTorch | No export found |

**⚠️ Broken export to avoid:** [onnx-community/open-jev-deberta-v3-large-ONNX](https://huggingface.co/onnx-community/open-jev-deberta-v3-large-ONNX)
advertises `model.onnx` at **0.5 MB** and `model_q4.onnx` at 0.6 MB for a DeBERTa-v3-large model whose
real weights are 1655.7 MB `[V]`. The weights were not uploaded. Do not cite this as an ONNX export.

### Smallest / most on-device-friendly — ranked

1. **Laya** (421M / 803.6 MB, Apache-2.0) — **the only one with a real, working, published ONNX export**
   and a *non-autoregressive* architecture. Non-autoregressive is the decisive property: one forward pass,
   no KV cache, no token loop, fixed input shape → this is the shape an NPU/ONNX runtime actually likes.
   Still ~800 MB and ~400M params, which is heavy for a mid-range phone.
2. **`shreyanbr/system-one-distilled` / `DavidHatley/system-one-mini`** (264–270 MB) — genuinely small and
   Apache-2.0, but they are single-encoder classifiers. You are buying a logistic regression with a
   transformer backbone.
3. **`IamBusy/OpenJev-0.6B`** — 4.4 MB adapter, but only meaningful on top of a full 0.6B base.

**Nothing in this table is vision-capable except `laya-vision-smolvlm-256m`, which is non-commercial `[V]`.**

---

## (B) Small VLMs and GUI-grounding models

| Name | URL | Params | Weights on disk | License | Base / arch | ONNX? |
|---|---|---|---|---|---|---|
| **SmolVLM-256M-Instruct** | [HuggingFaceTB/SmolVLM-256M-Instruct](https://huggingface.co/HuggingFaceTB/SmolVLM-256M-Instruct) | 256M | 489.3 MB safetensors; **quantized ONNX: decoder 130.9 MB + vision 89.9 MB + embed 27.1 MB ≈ 248 MB** | **Apache-2.0** | Idefics3 / SmolLM2-135M | **Yes, official, int8/uint8/q4/q4f16** |
| SmolVLM-500M-Instruct | [HuggingFaceTB/SmolVLM-500M-Instruct](https://huggingface.co/HuggingFaceTB/SmolVLM-500M-Instruct) | 500M | 968 MB; quantized ONNX decoder 348 MB | Apache-2.0 | Idefics3 / SmolLM2-360M | Yes |
| SmolVLM2-256M-Video | [HuggingFaceTB/SmolVLM2-256M-Video-Instruct](https://huggingface.co/HuggingFaceTB/SmolVLM2-256M-Video-Instruct) | 256M | ~490 MB | Apache-2.0 | SmolVLM-256M | Yes |
| **Moondream2** | [vikhyatk/moondream2](https://huggingface.co/vikhyatk/moondream2) | ~2B | **3676 MB** | Apache-2.0 | custom | Community ONNX only |
| **Florence-2-base-ft** | [microsoft/Florence-2-base-ft](https://huggingface.co/microsoft/Florence-2-base-ft) | 0.23B | 442 MB; **ONNX int8 ~93.6 + 89.4 + 41.6 ≈ 225 MB** | **MIT** | DaViT + Bart | **Yes** — [onnx-community/Florence-2-base-ft](https://huggingface.co/onnx-community/Florence-2-base-ft) |
| Florence-2-large-ft | [microsoft/Florence-2-large-ft](https://huggingface.co/microsoft/Florence-2-large-ft) | 0.77B | ~1.5 GB | MIT | DaViT + Bart | Yes |
| Qwen2-VL-2B-Instruct | [Qwen/Qwen2-VL-2B-Instruct](https://huggingface.co/Qwen/Qwen2-VL-2B-Instruct) | 2B | ~4.4 GB; ONNX int8 1474 + 1270 MB | Apache-2.0 | Qwen2-VL | Yes but ~2.7 GB quantized |
| Qwen2.5-VL-3B-Instruct | [Qwen/Qwen2.5-VL-3B-Instruct](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct) | 3B | ~7 GB | **`qwen-research`** ⚠️ *not* Apache — research license | Qwen2.5-VL | Community ONNX |
| **PaddleOCR-VL** | [PaddlePaddle/PaddleOCR-VL](https://huggingface.co/PaddlePaddle/PaddleOCR-VL) | 0.9B (ERNIE-4.5-0.3B) | **1828 MB** | **Apache-2.0** | ERNIE-4.5-0.3B-Paddle | [litert-community/PaddleOCR-VL-1.6](https://huggingface.co/litert-community/PaddleOCR-VL-1.6) — **`.litertlm` 1325.9 MB** (LiteRT = Google's on-device runtime, *not* Huawei) |
| **OmniParser v2.0** | [microsoft/OmniParser-v2.0](https://huggingface.co/microsoft/OmniParser-v2.0) · [GitHub](https://github.com/microsoft/OmniParser) (25427★) | icon_detect (YOLO) + icon_caption (Florence-2) | **icon_caption 1034 MB + icon_detect 39 MB** | **MIT** (HF) / **CC-BY-4.0** (GitHub) ⚠️ mismatch | YOLOv8 + Florence-2 | **icon_detect ONNX: 11.7 MB fp32, 3.2 MB int8, 5.9 MB fp16** — [onnx-community/OmniParser-icon_detect_640x640](https://huggingface.co/onnx-community/OmniParser-icon_detect_640x640) |
| **ShowUI-2B** | [showlab/ShowUI-2B](https://huggingface.co/showlab/ShowUI-2B) · [GitHub](https://github.com/showlab/ShowUI) (1902★) | 2B | **4214 MB** | **MIT** | Qwen2-VL-2B | **No ONNX found** |
| OS-Atlas-Base-7B | [OS-Copilot/OS-Atlas-Base-7B](https://huggingface.co/OS-Copilot/OS-Atlas-Base-7B) | 7B | ~16 GB | Apache-2.0 | Qwen2-VL-7B | GGUF only |
| OS-Atlas-Base-4B | [OS-Copilot/OS-Atlas-Base-4B](https://huggingface.co/OS-Copilot/OS-Atlas-Base-4B) | 4B | ~8 GB | Apache-2.0 | InternVL2-4B | No |
| UI-TARS-2B-SFT | [ByteDance-Seed/UI-TARS-2B-SFT](https://huggingface.co/ByteDance-Seed/UI-TARS-2B-SFT) | 2B | ~4.5 GB | Apache-2.0 | Qwen2-VL-2B | **No ONNX** |
| UI-TARS-7B-SFT | [ByteDance-Seed/UI-TARS-7B-SFT](https://huggingface.co/ByteDance-Seed/UI-TARS-7B-SFT) | 7B | ~16 GB | Apache-2.0 | Qwen2-VL-7B | No |
| UI-TARS-1.5-7B | [ByteDance-Seed/UI-TARS-1.5-7B](https://huggingface.co/ByteDance-Seed/UI-TARS-1.5-7B) | 7B | **31632 MB** | Apache-2.0 | Qwen2.5-VL-7B | No |
| Aguvis-7B-720P | [xlangai/Aguvis-7B-720P](https://huggingface.co/xlangai/Aguvis-7B-720P) · [GitHub](https://github.com/xlang-ai/aguvis) (392★) | 7B | **15809 MB** | **none declared** [?] | Qwen2-VL-7B | GGUF only |
| Aria-UI-base | [Aria-UI/Aria-UI-base](https://huggingface.co/Aria-UI/Aria-UI-base) | ~3.9B MoE (Aria) | ~9 GB | Apache-2.0 | rhymes-ai/Aria | No |

**Searches that returned nothing** (evidence of absence, not absence of evidence): HF search for
`showui onnx` → 0 results; `ui-tars onnx` → 0 results. **No ONNX or mobile-quantized export exists for
ShowUI, UI-TARS, OS-Atlas, or Aguvis** `[V]`.

### Which are small enough for a mobile NPU?

| Tier | Models | Verdict |
|---|---|---|
| **Plausibly mobile** (<300 MB quantized) | SmolVLM-256M (≈248 MB int8 ONNX), Florence-2-base-ft (≈225 MB int8 ONNX), OmniParser icon_detect alone (3.2 MB int8) | The only realistic candidates. |
| **Borderline** (0.5–1.5 GB) | PaddleOCR-VL (1.8 GB / 1.3 GB LiteRT), SmolVLM-500M, Florence-2-large | Heavy but not absurd |
| **Not mobile** (>2 GB) | Moondream2, ShowUI-2B, Qwen2-VL-2B, Qwen2.5-VL-3B, and every 4B/7B GUI agent | Forget it on an 8020-class part |

**License red flags:** `thaitea/laya-vision-smolvlm-256m` is **CC BY-NC-SA 4.0** (non-commercial) `[V]`;
`Qwen2.5-VL-3B-Instruct` is **`qwen-research`, not Apache** `[V]` — a widely-repeated error;
`OmniParser` is **MIT on HF but CC-BY-4.0 on GitHub** `[V]` — check which artifact you ship;
`Aguvis-7B-720P` declares **no license** `[V]`.

---

## (C) What a UI-automation agent actually needs — decomposed

### (a) Locate UI elements / read on-screen text

| Sub-problem | Smallest viable approach | Smallest *neural* option |
|---|---|---|
| Read text on screen | **Platform OCR** — HarmonyOS Core Vision Kit text recognition, or PaddleOCR mobile / Tesseract | PaddleOCR-VL (1.8 GB) is *massive overkill* for "find the 领取 button" |
| Find a tappable element | **Template matching** (OpenCV `matchTemplate`) if the UI is stable; **accessibility tree** if available | OmniParser **icon_detect alone** — 3.2 MB int8 ONNX, 11.7 MB fp32 |
| Understand layout semantics | Not needed for a repetitive task | Florence-2-base-ft (225 MB int8) if you truly need grounding |

**Key asymmetry:** OmniParser's *detector* is 3.2 MB quantized. Its *captioner* is 1034 MB. For
"where do I tap", you need the detector, not the captioner. Most people ship both and pay 300× for nothing.

### (b) Decide the next action

For "claim daily coins in a video app", enumerate the actual decision space:

- Is the app in the foreground? (deterministic)
- Is there a coin/reward icon on screen? (template match → boolean)
- Is a "领取"/"Claim" button present and enabled? (template match / OCR string match → boolean)
- Did a cooldown timer appear? (OCR digits, or absence of the button)
- Did a dialog/ad appear? (template match on the close-X)

That is **a finite-state machine with 5–8 states and boolean transitions**. There is no
distribution over candidate actions to score. A decision model that returns "calibrated probabilities
over a candidate set" is answering a question this task never asks.

### (c) Emit coordinates

- **Template matching** returns the match location directly — no separate coordinate model needed.
- **Accessibility tree** returns the node bounds directly.
- **OCR** returns bounding boxes per text line.
- A GUI-grounding VLM (ShowUI/UI-TARS/OS-Atlas) emits coordinates as text tokens — 2–16 GB of model to
  produce two integers you could have read off a template match.

### Is a neural decision model needed at all?

**No.** Honest decomposition of the decision complexity:

| Task class | Decision complexity | Right tool |
|---|---|---|
| Claim daily coins / check-in / repetitive reward loop | **Trivial** — fixed UI, ≤8 states, boolean transitions | Template matching + OCR + FSM. Zero neural nets, or one tiny CNN classifier. |
| Navigate an *unseen* app described in natural language | **High** — open-ended grounding + planning | GUI VLM. But 2B+ params, so cloud/PC, not NPU. |
| Robust to UI redesign / A-B tests | **Medium** | Retrain a small detector on new screenshots; still no LLM. |

The trap is reasoning from "Jev is a decision model, so I need a decision model." Jev exists to answer
*open-ended typed questions about unstructured text at scale*. "Is the claim button visible?" is not
that kind of question — it is a vision problem with a boolean answer.

---

## (D) MindSpore Lite / NNRt reality check — can it run a transformer on Kirin NPU?

### The documented limits `[V]`

**Source:** MindSpore Lite *List of Hardware Backends Supported by MindSpore Lite*,
<https://www.mindspore.cn/lite/docs/en/master/reference/operator_list_lite.html>. The table has **198 operators**
and a **"Kirin NPU"** column. I parsed it programmatically. **Only 58 operators have any Kirin NPU support**,
and **every one is FP16-only** — the NPU column contains no Int8 and no FP32 entries.

**Operators a transformer needs that have NO Kirin NPU implementation `[V]`:**

| Operator | Why it matters | CPU | Kirin NPU | GPU | Ascend |
|---|---|---|---|---|---|
| `LayerNormFusion` | **Every** transformer block | FP16/FP32/Int8 | **`-`** | FP16/FP32 | FP16 |
| `EmbeddingLookupFusion` | Token embedding lookup | FP32 | **`-`** | **`-`** | FP16 |
| `Erf` | GELU activation | FP16/FP32 | **`-`** | **`-`** | FP16 |
| `RealDiv` | Softmax denominator / attention scaling | FP16/FP32 | **`-`** | **`-`** | FP16 |
| `Shape` | Dynamic shape handling | all | **`-`** | FP16/FP32 | FP16 |
| `Squeeze` | Attention head reshaping | all | **`-`** | FP16/FP32/Int32 | FP16 |
| `LogSoftmax` | — | FP16/FP32 | **`-`** | **`-`** | FP16 |
| `TopKFusion` | Sampling | all | **`-`** | **`-`** | FP16 |
| `PowFusion` | — | FP16/FP32/Int8 | **`-`** | FP16/FP32 | FP16 |
| `OneHot`, `Where`, `Fill`, `Range`, `ScatterNd`, `CumSum`, `BroadcastTo`, `GatherNd` | assorted | — | **`-`** | — | — |

**Operators that ARE supported on Kirin NPU** (the 58) include `MatMulFusion`, `Softmax`, `Transpose`,
`Reshape`, `Concat`, `SliceFusion`, `StridedSlice`, `Gather`, `DivFusion`, `MulFusion`, `SubFusion`,
`AddFusion`, `ReduceFusion`, `Activation`, `FullConnection`, `Conv2DFusion`, `ArgmaxFusion`, `Cast`,
`ExpandDims`, `Unsqueeze`, `Split`, `Sqrt`, `Rsqrt`, `Neg`, `Log`, `Sin`, `Cos`, `Equal/Greater/Less`,
`PadFusion`, `TileFusion`, `ScaleFusion`, `InstanceNorm`, `Eltwise`.

**So: the attention matmuls are fine, but the moment you hit LayerNorm or the embedding table, the
graph falls off the NPU.** In a heterogeneous context, every fallback costs a sync + DDR round-trip,
which routinely costs more than the NPU saved — and this is the documented failure mode.

### Corroborating limits

| Limit | Evidence |
|---|---|
| **No transformer/LLM in the validated model list** | MindSpore Lite *Model List* has exactly five categories: Image Classification, Object Detection, Image Segmentation, Style Transfer, Scene Detection. **No NLP, no transformer, no LLM.** `[V]` <https://www.mindspore.cn/lite/docs/en/master/reference/model_lite.html> |
| **Quantization is INT8; the NPU is FP16** | MindSpore Lite PTQ supports weight/full/dynamic quant, all **int8** `[V]` <https://www.mindspore.cn/lite/docs/en/master/advanced/quantization.html>. The Kirin NPU column is FP16-only. **The quantization story and the NPU backend do not intersect.** |
| **Kirin NPU path is Android + HiAI DDK, not OHOS** | The Kirin NPU integration page requires `HUAWEI HiAI DDK` and `libhiai*.so`, builds with `-I arm64`, and tells you to `adb`-push to "an Android phone equipped with Kirin NPU chips" `[V]` <https://www.mindspore.cn/lite/docs/en/master/advanced/third_party/npu_info.html> |
| **OHOS support is CPU-only** | MindSpore Lite 2.10.0 release notes: *"Added OHOS cross-compilation support for **CPU inference** and on-device training."* `[V]` <https://www.mindspore.cn/lite/docs/en/master/RELEASE.html> |
| **NNRt: 56 operators, sync only** | *"NNRt目前支持常用算子56个"*, *"NNRt目前仅支持同步推理"*, no multi-thread composition, no emulator, and *"NNRt仅可提供已在底层接入的AI加速硬件的AI推理能力，**不提供CPU等通用硬件上的AI推理能力**"* `[V]` (Huawei doc API, `neural-network-runtime-kit-introduction`) |
| **Dynamic shapes** | MindSpore Lite `converter_lite` supports `--inputShape`; dynamic dims exist but the NPU path requires fixed shapes in practice, and `Shape` is not NPU-supported. **KV-cache as a growing buffer is not something this operator set supports.** |

### Has anyone actually run a transformer LLM on a Kirin NPU?

**Via MindSpore Lite / NNRt: I found no repo and no report. Say plainly: nobody has published this.**
NNRt's 56-op list plus the missing LayerNorm/EmbeddingLookup make it structurally implausible, and the
validated model list contains zero NLP models.

**Via CANN Kit / LLM Engine: YES — and this is the real answer.** I found concrete, code-bearing repos:

| Repo | What it actually does |
|---|---|
| [nowang6/kirin-npu-llm](https://github.com/nowang6/kirin-npu-llm) (0★, no license, 3 commits Jul 2026) | **Full conversion + deployment pipeline.** `model-converter/` takes **Qwen2.5-1.5B-Instruct**, PTQ-quantizes with Huawei's `dopt` tool (`W_BITS=4`, `ACT_BITS=16`, `block_size=128`), exports ONNX, then compiles to `.om` with Huawei's `omg` using **`--platform=kirin9020`** and explicit `past_key_in0..27` / `past_value_in0..27` KV-cache tensors at `2048,2,1,128`, `--dynamic_dims="1,1,1,1,1;64,64,64,64,64"` (prefill 64 / decode 1), `--target=omc`. `engine_ohos/` cross-compiles `llm_bin`/`llm_eval` for **`aarch64-linux-ohos`** and ships `libhiai_llm_engine.so` + `libneural_network_runtime.so`. README is Chinese: *"在 HarmonyOS / OpenHarmony 设备上，通过命令行运行 Qwen2.5 等大模型推理"* `[V]` |
| [nowang6/kirin_npu_llm_app](https://github.com/nowang6/kirin_npu_llm_app) (0★, no license) | **A complete HarmonyOS ArkTS app** that loads the `.om` via `LLMEngineInit`/`LLMEngineGenerateAsync`, with `executor.json` for **Qwen3-1.7B** (`num_hidden_layers: 28`, `kv_cache_max_len: 2048`, `prefill_len: 64`, `decode_len: 1`, `embedding_input_type: "int8"`) and **Qwen2-1.5B**. Streams tokens to the UI through `napi_create_threadsafe_function`. Includes a full sequence diagram of the NAPI↔CANN inference path. `[V]` |
| [nowang6/kirin_npu_llm](https://github.com/nowang6/kirin_npu_llm) (0★, Jan 2026) | Earlier version, same shape: `npu_tuned_model/{qwen2,qwen3,glm}`, `export_model_single_qwen2.py`, `--platform=kirin9020`. `[V]` |

**How much should you trust this?** It is real code with real Huawei toolchain invocations, real
`libhiai_llm_engine.so` binaries, and a real ArkTS app. But: **0 stars, no license, no issues, no
independent reproduction, and the only performance numbers are in a README example block**
(`decode_speed_tok_s: 34.8`, `decode_ms_per_token: 28.76`) which I could **not** verify against a device.
Treat the *feasibility* as demonstrated `[V]` and the *numbers* as unverified `[T]`.

### The Kirin 8020 gap — the single most important caveat

Huawei's own CANN LLM Engine doc, read through their doc API `[V]`:

> **模型要求:** 当前版本支持 Qwen2.5-1.5B、DeepSeek-R1-Distill-Qwen-1.5B、Glm-1.5b、Qwen2.5-7B-Instruct、Qwen3-8B模型。
> **硬件要求:** **kirin X90平台。**

**The officially supported LLM hardware is `kirin X90` — flagship only. Kirin 8020 is not on that list.**

Meanwhile the DDK ships platform plugins for **`kirin9020`**, **`kirin9030`**, **`kirinx90`** `[V]`
(Huawei doc API, `cannkit-preparations`; `DDK-tools-next-6.1.1.0`). And the hobby repo compiles with
`--platform=kirin9020` `[V]`.

**Do not confuse `kirin9020` with `Kirin 8020`.** These are different part numbers. `kirin9020` is the
platform-plugin name used by the DDK; Kirin 8020 is the mid-range SoC in the nova 15. Whether the
`kirin9020` OMG plugin targets the 8020 silicon, or whether the official LLM Engine wrapper is
runtime-gated to X90 regardless of what `.om` you built, is **exactly the question I could not resolve `[?]`**.
This is the one thing to test on real hardware before committing to any NPU design.

---

## (E) Kirin 8020 NPU — TOPS and plausible parameter count

**There is no published TOPS figure for the Kirin 8020 NPU.** `[V]`

From [cpudb's Exynos 1580 vs Kirin 8020 comparison](https://www.cpudb.cc/compare/samsung-exynos-1580-vs-hisilicon-kirin-8020) `[V]`:

| Field | Samsung Exynos 1580 | HiSilicon Kirin 8020 |
|---|---|---|
| AI NPU | Yes | **Da Vinci** |
| **Theoretical Performance** | **14.7 TOPS** | **`-` (blank)** |
| Class | Mid range | **Mid range** |
| Process | 4 nm Samsung | **7 nm SMIC** |
| CPU | 1×2.9 + 3×2.6 + 4×1.95 GHz | 1×2.285 + 3×2.05 + 4×1.3 GHz |
| GPU | Xclipse 540 | **Maleoon 920 @ 840 MHz** |
| Announced | Oct 2024 | May 2025 |

**The "14.7 TOPS" that circulates as a Kirin 8020 number is the Exynos 1580's figure, sitting in the
adjacent column of the same table.** Anyone quoting a Kirin 8020 TOPS number is reading this table wrong
or guessing. The companion NPU note reached the same conclusion independently `[V]`.

Huawei's own launch material gives **relative deltas only** — NPU +128%, CPU multi-core +52%, GPU +26%
vs the previous generation, with **no baseline disclosed** `[T]`. A percentage without a baseline is not
a TOPS figure.

### Plausible LLM parameter count — evidence-based, not extrapolated

The **only empirical anchor** is the working repo above: **Qwen2.5-1.5B and Qwen3-1.7B**, W4 weights /
A16 activations, 2048-token KV cache, 28 layers, compiled for `kirin9020` `[V]`.

So:

| Size | Assessment |
|---|---|
| **0.5B–2B, W4A16, ≤2048 ctx** | **Demonstrated** in a hobby repo targeting `kirin9020` `[V]` |
| 3B | Untested; likely possible but KV cache + weight traffic get painful |
| 7B–8B | **Officially X90-only** per Huawei's own doc `[V]`. Not plausible on an 8020. |
| **0.3B–0.5B (e.g. a decision head, SmolVLM-256M)** | **The sane target.** Comfortably inside the demonstrated envelope. |

**Do not extrapolate TOPS → params.** With no TOPS figure and no measured bandwidth, any "the 8020 can
run N billion parameters" claim is fabrication. The demonstrated band is 0.5–2B.

---

## (F) Blunt recommendation

### Is running a model on the NPU the right design for "read screen → decide → click"?

**No. Not for this use case.** Reasoning, in order of weight:

1. **The decision complexity does not justify a neural decision model.** "Claim daily coins" is a
   finite-state machine over 5–8 boolean observations. A calibrated distribution over a candidate set —
   which is what every model in table (A) produces — is the wrong output type for the problem.
2. **No Jev reproduction can see the screen.** Every one is text-only. You would still need a separate
   vision stage, which is where all the real difficulty lives.
3. **The NPU path is the riskiest possible place to put the least valuable component.** MindSpore
   Lite/NNRt cannot run a transformer `[V]`; the CANN path is X90-gated in official docs `[V]`; the one
   working example is a 0-star unlicensed repo `[V]`; and you cannot even measure NPU utilization on
   HarmonyOS `[V]`.
4. **HarmonyOS will fight you.** Continuous background inference has no suitable continuous-task type
   for non-2-in-1 devices, and sustained load gets you suspended or terminated `[V]`.

### What to actually build

**Tier 1 — ship this (days, not months):**

```
Screen capture → template match (OpenCV matchTemplate) for the claim button
              → OCR (HarmonyOS Core Vision Kit text recognition) for labels/cooldowns
              → deterministic FSM (idle → button_seen → tap → verify → cooldown → idle)
              → tap coordinate = the template match location
```

Zero neural networks. Runs on CPU. Fully debuggable. Survives UI redesign by swapping template images.
This solves "claim daily coins" outright.

**Tier 2 — add only if templates prove too brittle:**

- A **tiny CNN classifier** (MobileNet-class, <5 MB INT8) trained on your own screenshots to classify
  screen state ("claim button present" / "ad dialog" / "cooldown"). Runs on CPU in single-digit ms, or on
  the NPU via MindSpore Lite — this is exactly the CNN shape the NPU op table *does* support `[V]`.
- **OmniParser's icon_detect alone** (3.2 MB int8 ONNX) if you need to find *arbitrary* tappable icons
  rather than a known button. Ship the detector, **not** the 1 GB captioner.

**Tier 3 — only if the task genuinely becomes open-ended** ("do my daily routine across 5 apps I've never
seen"): use a GUI VLM, but run it **cloud-side or on a PC**, not on the phone. 2B–16B params with no
ONNX export and no NPU op coverage is not a phone workload.

**If you insist on on-device neural inference, the single best candidate is Laya** (Apache-2.0, 421M,
**non-autoregressive**, ONNX export already published) — but note it is text-only, so it cannot see the
screen, and it is still ~800 MB.

**Do the A/B harness first.** Same model, `targetDevice=CPU` vs `nnrt`/`HIAI_F`, same input, compare
latency — that delta is the only honest NPU evidence you can produce on this platform `[V]`.

---

## (G) What I could NOT confirm

| # | Unconfirmed | Why it matters |
|---|---|---|
| 1 | **Whether Kirin 8020 can run the CANN LLM Engine at all.** Official doc says hardware = `kirin X90平台` `[V]`; DDK ships a `kirin9020` plugin and a hobby repo uses it `[V]`. Whether `kirin9020` plugin ≠ Kirin 8020 silicon, and whether the LLM Engine runtime is X90-gated, is unresolved `[?]`. | **This is the gating question for any NPU LLM plan.** Test on real hardware. |
| 2 | **Kirin 8020 NPU TOPS.** No official figure. cpudb blank; "14.7 TOPS" is the Exynos column. `[?]` | Any absolute performance claim is unsupported. |
| 3 | **Measured performance of any LLM on a Kirin NPU.** The `nowang6` repo's `decode_speed_tok_s: 34.8` is a README example block, not a reproduced benchmark. `[?]` | No basis for a latency budget. |
| 4 | **`onnx-community/open-jev-deberta-v3-large-ONNX`** advertises 0.5 MB for a 1.6 GB model — weights appear missing. Unusable. `[V]` | Don't cite it. |
| 5 | **Aguvis license.** `xlangai/Aguvis-7B-720P` declares no license on HF `[V]`. | Cannot ship. |
| 6 | **Laya's real-world accuracy on *your* task.** The card is candid: base checkpoints are **near chance zero-shot** (0.362 vs 0.461 majority baseline) and 0.766 comes from a fine-tune on that benchmark's own split `[V]`. | Laya is "a fast base to specialise", not an off-the-shelf decision engine. |
| 7 | **Whether any GUI-grounding model has been run on a Kirin NPU.** No evidence found, any model, any size. `[?]` | Absence of evidence. |
| 8 | **NanoJev's license.** HF metadata has no license field; card says code MIT + Qwen upstream terms. Ambiguous. `[?]` | Legal risk. |
| 9 | **MindSpore Lite's ONNX-import fidelity for transformer graphs specifically.** ONNX import is documented `[V]`, but I found no report of anyone importing a full transformer and running it on the Kirin NPU backend. | The op-coverage analysis above is strong evidence it would fail, but is inference from the op table, not a reproduction. |
| 10 | **Web search was unavailable** (HTTP 402 on the search endpoint) for the whole session. Everything came from direct API/doc fetches. A few queries — notably Chinese-language Kirin 8020 teardown/benchmark coverage — never ran. | Re-run those before finalising hardware assumptions. |

---

## Sources

**HuggingFace** (via JSON API + file tree):
[convaiinnovations/laya](https://huggingface.co/convaiinnovations/laya) ·
[laya-multilingual](https://huggingface.co/convaiinnovations/laya-multilingual) ·
[laya-typed-decisions](https://huggingface.co/convaiinnovations/laya-typed-decisions) ·
[Mattepiu/laya-onnx](https://huggingface.co/Mattepiu/laya-onnx) ·
[sevenreasons/laya-onnx-fp16](https://huggingface.co/sevenreasons/laya-onnx-fp16) ·
[thaitea/laya-vision-smolvlm-256m](https://huggingface.co/thaitea/laya-vision-smolvlm-256m) ·
[C-Tianyu/NanoJev](https://huggingface.co/C-Tianyu/NanoJev) ·
[AlexWortega/openjev](https://huggingface.co/AlexWortega/openjev) ·
[IamBusy/OpenJev-0.6B](https://huggingface.co/IamBusy/OpenJev-0.6B) ·
[bespokelabs/Bespoke-Nimble-9B](https://huggingface.co/bespokelabs/Bespoke-Nimble-9B) ·
[dwidlee/systemone-lite-0.5b](https://huggingface.co/dwidlee/systemone-lite-0.5b) ·
[shreyanbr/system-one-distilled](https://huggingface.co/shreyanbr/system-one-distilled) ·
[DavidHatley/system-one-mini](https://huggingface.co/DavidHatley/system-one-mini) ·
[com-kotobalabs/open-jev-deberta-v3-large](https://huggingface.co/com-kotobalabs/open-jev-deberta-v3-large) ·
[HuggingFaceTB/SmolVLM-256M-Instruct](https://huggingface.co/HuggingFaceTB/SmolVLM-256M-Instruct) ·
[SmolVLM-500M-Instruct](https://huggingface.co/HuggingFaceTB/SmolVLM-500M-Instruct) ·
[SmolVLM2-256M-Video-Instruct](https://huggingface.co/HuggingFaceTB/SmolVLM2-256M-Video-Instruct) ·
[vikhyatk/moondream2](https://huggingface.co/vikhyatk/moondream2) ·
[microsoft/Florence-2-base-ft](https://huggingface.co/microsoft/Florence-2-base-ft) ·
[onnx-community/Florence-2-base-ft](https://huggingface.co/onnx-community/Florence-2-base-ft) ·
[Qwen/Qwen2-VL-2B-Instruct](https://huggingface.co/Qwen/Qwen2-VL-2B-Instruct) ·
[Qwen/Qwen2.5-VL-3B-Instruct](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct) ·
[PaddlePaddle/PaddleOCR-VL](https://huggingface.co/PaddlePaddle/PaddleOCR-VL) ·
[PaddlePaddle/PaddleOCR-VL-1.6](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6) ·
[litert-community/PaddleOCR-VL-1.6](https://huggingface.co/litert-community/PaddleOCR-VL-1.6) ·
[microsoft/OmniParser-v2.0](https://huggingface.co/microsoft/OmniParser-v2.0) ·
[onnx-community/OmniParser-icon_detect_640x640](https://huggingface.co/onnx-community/OmniParser-icon_detect_640x640) ·
[showlab/ShowUI-2B](https://huggingface.co/showlab/ShowUI-2B) ·
[OS-Copilot/OS-Atlas-Base-7B](https://huggingface.co/OS-Copilot/OS-Atlas-Base-7B) ·
[ByteDance-Seed/UI-TARS-2B-SFT](https://huggingface.co/ByteDance-Seed/UI-TARS-2B-SFT) ·
[ByteDance-Seed/UI-TARS-1.5-7B](https://huggingface.co/ByteDance-Seed/UI-TARS-1.5-7B) ·
[xlangai/Aguvis-7B-720P](https://huggingface.co/xlangai/Aguvis-7B-720P) ·
[Aria-UI/Aria-UI-base](https://huggingface.co/Aria-UI/Aria-UI-base)

**GitHub:**
[GitHub30/OpenJev](https://github.com/GitHub30/OpenJev) ·
[MoeclubM/PlayJev](https://github.com/MoeclubM/PlayJev) ·
[bespokelabsai/nimble](https://github.com/bespokelabsai/nimble) ·
[NandhaKishorM/laya](https://github.com/NandhaKishorM/laya) ·
[r33drichards/laya-vision](https://github.com/r33drichards/laya-vision) ·
[nowang6/kirin-npu-llm](https://github.com/nowang6/kirin-npu-llm) ·
[nowang6/kirin_npu_llm_app](https://github.com/nowang6/kirin_npu_llm_app) ·
[nowang6/kirin_npu_llm](https://github.com/nowang6/kirin_npu_llm) ·
[microsoft/OmniParser](https://github.com/microsoft/OmniParser) ·
[showlab/ShowUI](https://github.com/showlab/ShowUI) ·
[OS-Copilot/OS-Atlas](https://github.com/OS-Copilot/OS-Atlas) ·
[bytedance/UI-TARS](https://github.com/bytedance/UI-TARS) ·
[xlang-ai/aguvis](https://github.com/xlang-ai/aguvis)

**MindSpore Lite docs:**
[Operator/backend support list](https://www.mindspore.cn/lite/docs/en/master/reference/operator_list_lite.html) ·
[Model list](https://www.mindspore.cn/lite/docs/en/master/reference/model_lite.html) ·
[Quantization](https://www.mindspore.cn/lite/docs/en/master/advanced/quantization.html) ·
[Kirin NPU integration](https://www.mindspore.cn/lite/docs/en/master/advanced/third_party/npu_info.html) ·
[Release notes 2.10.0](https://www.mindspore.cn/lite/docs/en/master/RELEASE.html)

**Huawei official docs** (via `documentPortal` JSON API):
CANN Kit 简介 (`cannkit-introduction`) · CANN 开发准备 (`cannkit-preparations`) ·
CANN 基本架构 (`cannkit-basic-architecture`) · CANN 兼容性说明 (`cannkit-compatibility-rule`) ·
CANN LLM 简介 (`cannkit-llm-summary`) · NNRt Kit 简介 (`neural-network-runtime-kit-introduction`) ·
NNRt 对接开发指导 (`neural-network-runtime-guidelines`)

**Hardware:** [cpudb Exynos 1580 vs Kirin 8020](https://www.cpudb.cc/compare/samsung-exynos-1580-vs-hisilicon-kirin-8020)

---

## 附录（2026-09-21 更新）：Jev API 一手资料核实 + 「LPR + Jev 智慧城市」架构评估

头部「Given, not re-verified」里对 Jev 的判断（API-only / 纯文本 / 无视觉 / 中国大陆不可用）
本轮用一手来源**复核**，前半成立、最后一条**未能从官方文档证实**（官方页面无区域声明），
其余关键事实如下（全部 `[V]` 本轮一手核实）：

**来源**：[typesafe.ai 官方发布博客](https://typesafe.ai/blog/introducing-system-one-models-and-jev)（2026-09-15）、
[API 使用文档](https://www.jevtypesafeai.com/how-to-use)（独立站点，内容与 Cloudflare 官方文档互证）、
[Cloudflare AI docs `typesafe/jev`](https://developers.cloudflare.com/ai/models/typesafe/jev/)。

**Jev 是什么**（System One 决策模型，不是 LLM）：
- **单端点** `POST https://api.typesafe.ai/v1/systemone`（Bearer，`TYPESAFE_API_KEY`）；
  也可走 **Cloudflare Workers AI**（`typesafe/jev`）与 **Vercel AI Gateway**。
- 输入 `state`（字符串/JSON/文本数组，连同 questions 共 ≤64k tokens）+ `questions` 映射；
  一次往返并行评估多个问题。
- **三种题型**：`choice`（≤255 个带说明的候选项，返回选中项 + 各项概率 + 置信度）、
  `score`（2–10 档刻度，返回可分数分数 + 全分布）、`noul`（校准 yes/no 概率）。
  输出**类型化、不会 schema 错误、无幻觉字符串**；每题自带校准置信度。
- **延迟 70–500 ms**（官方自报端到端）；**价格 $0.042/MTok 输入、输出免费**；
  限流 250k tokens/s、1200 req/min。
- **无视觉**：官方博客原文 *"The demo is on structured state as a data structure with text,
  not on images (yet…)"* —— 图像输入尚在路线图，不是现在。
- **正式 access 是 waitlist**（early access）；区域可用性官方未声明 ——
  中国大陆可达性**需要实测**，不能信旧笔记的断言。

**「手机 LPR（NPU + 60fps）+ Jev 代替多模态 Agent」评估**（给智慧城市交通模拟）：

1. **方向是成立的，而且恰好是 Jev 的正确用法**。多模态 Agent 把「看图 + 决策」绑在一起，
   端侧跑不动、云端 3–329 s 不可用；而本项目手机端已经把视觉问题解成结构化事件
   （车牌串 / 牌色 / 置信度 / 时间戳）。Jev 要的输入恰好就是这种 state 对象 ——
   **感知归感知（端侧专用流水线），决策归决策（Jev）**，分层是对的。
2. **粒度必须按事件不按帧**。60fps 帧流直接喂 API 是 60 调用/秒的浪费（官方 Doom demo
   10 qps ≈ $7/h）；正确做法：端侧 FSM 先做去抖/去重/轨迹聚合，**每辆车/每事件一次调用**
   （Jev 支持单调用批量多问题）。典型 state ≈ 200–400 tokens，成本可忽略。
3. **Jev 不是 Agent**：无工具调用、无记忆、无循环 —— 编排回路（事件队列、重试、
   降级）要自己写，这正是它「function call」定位的含义。
4. **置信度即路由**：`noul/score` 的置信度可做演示的阈值分流 —— 高置信自动决策，
   低置信上送截图或人工（这正是官方建议用法）。
5. **两条硬风险**：① 大陆网络对 `api.typesafe.ai` / Cloudflare AI 的可达性**未验证**，
   演示前必须真机 ping 通 + 准备端侧规则引擎兜底；② waitlist 拿 key 有时延。
6. **与论文关系**：Jev 在云，与本论文的端侧主张不冲突 —— 手机侧做**感知**，
   恰好证明「感知下沉端侧 + 决策外置」的架构，反而可作为 RQ3 的应用叙事。

---

## 附录二（2026-09-22）：Jev 做 Browser Use / Computer Use 的可行性

**起因**：用户想用 Jev 做 Browser Use / Computer Use。原话：

> 现在的 Computer Use 只有 Codex 比较好用，其他都是**截图然后再丢回给大模型，
> 让大模型输出截图的坐标，再模拟点击，就非常非常慢**。我真的是用吐了。

**结论**：**能做，但用户诊断的瓶颈找错了地方；而且手机端方向不成立。**

### 1. Jev 官方明确不做感知

官方文档原文：*"Jev currently accepts text input only… Images, audio, and video are
not supported (yet)"*。[官方] `docs.typesafe.ai/concepts/system-one`

TypeSafe 自己的立场（Tom's Hardware 引述）：「Jev 的强项不是像 agent 那样行动或做宽泛
推理，开放式任务更适合 LLM」。[官方/媒体]

⇒ **Jev 是「决策函数」，不是感知模型，也不是规划器。** HN 上有人说「这就是个
zero-shot classifier」，Almeida 回「exactly right!」。[社区]

### 2. 但确实有人把它接进 browser loop 了

**APUS AI Lab 的 `fast-browser-use`**（MIT）：复现 Jev「跳过自回归解码、隐状态直接打分」
的逻辑，用本地 Qwen3.5-9B 做**单 Token Logits 决策**——把页面**真实可见可点元素**整理成
候选元组 `(CLICK, btn_7)`，模型**只在候选集里单选**，从机制上消灭「选择器幻觉」。
[源码] `github.com/APUS-AI-Lab/fast-browser-use`

这是现成的参考实现。

### 3. ⚠️ 关键纠正：截图**不是**瓶颈

OSWorld-Human 论文（arXiv 2506.16042, MLSys 2026）实测的耗时占比 [论文]：

| 阶段 | Agent S2 | GTA1 |
|---|---|---|
| 规划 planning | **53.5%** | **74.6%** |
| 反思 reflection / 判断 | **33.6%** | **22.5%** |
| **截图 + 动作执行** | **约 3.3%** | **约 1.1%** |

**规划 + 反思合计 87–97%，截图与键鼠事件只占几个百分点。**

补充量级：第 t 步要背前 t−1 步截图，**任务后期单步耗时可达初期 3 倍**；
最优 agent 步数仍是人类参考轨迹的 **1.4–2.7 倍**。
本地 UI-TARS-2B 单次元素定位 ~1.2 s、读全屏文字 ~3 s；Playwright MCP 30 任务
468–493 s，browser-use 21 任务 1870 s。[社区/源码]

⇒ **真正该优化的是「减少模型调用次数 + 压缩上下文」，不是「换更快的点击」。**
用户「用吐了」的那个慢，主因是**每一步都在重新规划**。这恰好是 Jev 的甜区
（70–500 ms、$42/B input）。

### 4. 不用视觉的路径：Browser 成熟，手机端堵死

**Browser（成熟且是主流）**：browser-use（DOM + a11y 树，10 万+ stars）、
Playwright MCP（a11y snapshot，简单页 ~200–400 token）、Stagehand、Vercel agent-browser
—— **全部收敛到 accessibility tree**。

速度：整页 a11y 树 **2.4 KB** vs 同页 1000px JPEG **16 KB** → **6–10×**；
且 ref（`link "submit" @e12`）比像素坐标稳定。[社区]

> ⚠️ **但要诚实**：WebVoyager 原论文里，**纯文本（a11y 树）只有 39–40.1%**，
> 多模态 55.7–59.1%。CHI 2026 还发现限制为纯键盘（完全依赖结构）时成功率 78%→42%。
> [论文] **DOM 方案快、便宜，但只在结构良好的页面可靠。**

**HarmonyOS 手机端：方向不成立**（本次重新核实，旧结论仍成立且更严）：

- `AccessibilityExtensionAbility` 的 `onConnect` / `onDisconnect` / `onAccessibilityEvent` /
  `onKeyEvent` **全部自 API 12 起 deprecated**。[官方]
- 更关键：`AccessibilityExtensionContext` 的 `getWindowRootElement`、`getFocusElement`、
  `injectGesture`（API 10 起废弃）、`injectGestureSync`、`AccessibilityElement.performAction`
  （即「注入点击」）**全部自 API 12 起 deprecated，且同页未给出未废弃的替代接口**。[官方]
- 华为开发者问答回复原话：「**由于安全原因，无障碍的节点查询、模拟操作等能力不再对三方
  开放了**」；「替代接口仅限系统应用使用」。[社区]
- `ohos.permission.ACCESSIBILITY` 属受限权限，需 AGC 逐个审核 + 视频说明。[官方]
- **唯一旁路是 PC 侧 `hdc shell uitest dumpLayout`** —— 官方支持导出任意前台应用的
  控件树（`type/text/id/bounds/clickable`），但 `uitest_server` 是特权守护进程，
  **不是纯手机端三方应用能力**，属**调试态**方案。[官方/源码]

**Windows（CPU-only，用户的实际环境）**：UI Automation / pywinauto 能读任意应用的 UIA 树
并注入点击，是**最现实的 no-vision 路径**。[?] 建议实测。

### 5. 建议架构与成熟度

```
感知层(代码) → 结构化状态(代码) → 决策层(Jev/LLM) → 动作层(代码)
```

| 层 | 职责 | 可行工具 |
|---|---|---|
| 感知 | 把界面变成**文本**，绝不出图 | Browser：Playwright a11y snapshot；Windows：pywinauto/UIA；手机：`hdc uitest dumpLayout`（PC 侧） |
| 结构化 | 候选动作元组 `(CLICK, btn_7)`、元素表、目标 URL/标题 | 纯代码，含可见性/遮挡/过期校验 |
| 决策 | 选动作 / 判完成 / 判元素匹配 | **Jev**（Choice/Noul/Score，70–500 ms）；长程规划交给 LLM |
| 动作 | 执行 + 事后校验 | Playwright click(ref)、UIA invoke；**用精确 URL/标题断言，不信模型自报的 DONE** |

**成熟度**：

| 目标 | 判断 |
|---|---|
| **Browser Use + Jev** | ✅ **可落地**（需自研 harness） |
| **Windows Computer Use（CPU-only）** | 🟡 需自研一些 |
| **HarmonyOS 手机端 Computer Use** | ❌ **不成立**（第三方 on-device） |

**最小可验证原型**：本机 Chrome 起 `--remote-debugging-port` → 抓 a11y snapshot →
转候选元组文本 → 调 Jev `Choice` 选元素 + `Noul` 判完成 → Playwright 按 ref 点击 → 循环。
**只度量三个数**：单步端到端耗时、Jev 单步耗时、任务步数 vs 人类基线。

### 6. 与本项目的关系

麒麟 NPU **跑不了 transformer**（LayerNorm / EmbeddingLookup 无 Kirin NPU 实现），
⇒ **端侧 VLM 直接排除**。这反而**强化**了「树优先、视觉兜底」的路线。

而**本项目的车牌识别恰好就是那个「视觉兜底层」**（端侧 OCR），
只在非文本界面（canvas / 图像按钮）才需要它。

⇒ **这件事值得做，但它是一个独立的 Browser Use 项目，不应塞进车牌识别。**
建议与「红果/抖音自动化」合并成同一个方向的下一步规划。

