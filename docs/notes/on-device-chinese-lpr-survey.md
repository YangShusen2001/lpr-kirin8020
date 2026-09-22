# On-Device Chinese License Plate Recognition (车牌识别 / LPR) — State of the Art for HarmonyOS Porting

Research note. Every claim below is tagged by how it was verified:

- **[V]** = read in a primary source during this session (README / LICENSE / official docs / paper text / GitHub API metadata)
- **[T]** = third-party/vendor claim read in a primary source (specific but self-reported, not independently reproduced)
- **[?]** = **could not verify this session** — treat as unconfirmed. Several web searches failed late in the session (search quota exhausted, HTTP 402), and a few vendor pages are JS-rendered and returned no body.

> **Biggest honest caveat up front:** I found **no verified measurement of a Chinese LPR detect+recognize pipeline on a mobile NPU** (Hexagon / APU / Da Vinci). Every latency number I could actually read is desktop CPU/GPU, or an illustrative value in vendor docs. That gap is flagged again in §3 and §E.

---

## 0. Headline findings for the HarmonyOS decision

1. **HarmonyOS has no official license-plate API.** The official on-device path is a *general* text recognizer — Core Vision Kit `textRecognition` (ArkTS). Plate recognition on HarmonyOS is assembled by **general OCR + plate-format rules**, not by a plate model. This is corroborated by the only shipping three-platform plugin that actually does it **[T]** (see §7).
2. **The AGPL trap is real and directly hits this use case.** Ultralytics' own license page says an Enterprise License is required for *"Any commercial product or service"*, *"Proprietary / closed-source software"*, and explicitly *"Embedded deployments in hardware, edge devices, robotics, cameras, or appliances"* and *"Using custom-trained or fine-tuned YOLO models in a proprietary or commercial setting"* **[V]**. A closed-source HarmonyOS app shipping YOLO weights is squarely in that list.
3. **HyperLPR3 is the pragmatic pick** (Apache-2.0 **[V]**, MNN-based, ships an Android SDK **[V]**) — but it has **no HarmonyOS port**, and its own TODO list admits double-layer plates, large angles, and a lightweight recognizer are unfinished **[V]**.
4. **A VLM does not belong in the on-device path.** The strongest paper I read states VLMs "are not yet viable substitutes for specialized recognition systems in practical deployments" **[V]**, and uses a 4B VLM only as a *low-confidence fallback* on a server-class machine.

---

## A. Candidate pipeline recommendation

Recommended architecture — **detect → rectify → recognize → rule-based post-process**, with all three network stages INT8-quantized and no VLM on device.

| Stage | Pick | Why | License |
|---|---|---|---|
| Detect | **Single-class plate detector with 4 corner keypoints** (YOLOv8n-pose / YOLO11n-pose class shape, or HyperLPR3's built-in detector) | Corners are needed for the perspective transform; single-class avoids colour-class confusion | **train your own** (see §E) |
| Rectify | 4-point perspective transform → fixed **400×120** crop | 400×120 is the exact corrected-plate size returned by a shipping commercial plugin **[T]** | n/a |
| Recognize | **LPRNet** (94×24, CTC, no RNN) | 0.34 GFLOPs, 95.0% on Chinese plates, designed for embedded **[V]** | Apache-2.0 (reimpl.) |
| Post-process | Province-abbreviation + structure regex + colour check + char-confusion fixes | Exactly what shipping plugins expose (`plateCheckedValid`, `plateCharsetValid`) **[T]** | n/a |
| Video | Multi-frame voting (see §4) | Standard practice; two papers found on it (§4) | n/a |

**Concrete picks**

- **If you must ship fast and accept "no HarmonyOS" today:** HyperLPR3 (Apache-2.0) + its Android SDK. Real, tested, 95–97% on entrance/exit scenes **[T]**.
- **If HarmonyOS is mandatory (the actual task):** you are building it yourself. Recommended stack:
  - Detector: a **self-trained** YOLOv8n/11n-pose on CCPD + CRPD + your own data — but **do not use the Ultralytics repo/weights in a closed product** (§E). Either train with a permissive framework, or buy the Enterprise License, or use HyperLPR3's detector.
  - Recognizer: **LPRNet** (94×24) or **PP-OCRv5_mobile_rec** (16 M **[V]**) fine-tuned on plate crops.
  - Runtime: **MindSpore Lite** or **ONNX Runtime / MNN** via the HarmonyOS NDK — see §6. *(I could not verify MindSpore Lite's ONNX-import and NPU specifics this session.)*
  - Fallback: general OCR (`textRecognition`) + plate rules, exactly as the shipping plugin does **[T]**.
- **Do not** put a VLM in the device pipeline. If you need one at all, make it a **server-side, confidence-gated fallback** (§5).

---

## B. Repo table

Star/fork/license values below are from the **GitHub REST API** (`api.github.com/repos/...`), read this session **[V]** — they are authoritative at fetch time, not scraped from badges.

| Name | URL | License | Size / budget | Mobile-ready? |
|---|---|---|---|---|
| **HyperLPR3** | https://github.com/szad670401/HyperLPR | **Apache-2.0** [V] | size not stated in README **[?]**; ~100 ms/720p frame on 2.2 GHz Haswell CPU **[T]** | **Yes, partially** — Android arm64/armeabi via MNN; Rockchip RKNPU; **no HarmonyOS** [V] |
| HyperLPR3 Android SDK | https://github.com/HyperInspire/hyperlpr3-android-sdk | Apache-2.0 [V] | JitPack `hyperlpr3-android-sdk:1.0.3` [V] | Android only [V] |
| **LPRNet** (paper) | https://arxiv.org/abs/1806.10447 | paper | **0.34 GFLOPs**, 94×24 input, 95.0% Chinese [V] | Designed for embedded; FPGA/CPU/GPU ports [V] |
| LPRNet_Pytorch | https://github.com/sirius-ai/LPRNet_Pytorch | Apache-2.0 [V] | community reimpl. (not Intel-official) | Yes (export to ONNX/NCNN) [?] |
| **PaddleOCR** | https://github.com/PaddlePaddle/PaddleOCR | **Apache-2.0** [V] | see §3 model sizes [V] | Yes — official Android/iOS deploy docs [V] |
| **CCPD** (dataset) | https://github.com/detectRecog/CCPD | **MIT** [V] | 355,013 imgs (2019) [V] | n/a (dataset) |
| **CRPD** (dataset) | https://github.com/yxgong0/CRPD | **NO LICENSE FILE** [V] ⚠ | ~30k imgs; **code not released** [V] | n/a |
| **CBLPRD-330k** (dataset) | https://github.com/SunlifeV/CBLPRD-330k | MIT [V] | 330,000 imgs [V] | n/a |
| yolo26-plate | https://github.com/we0091234/yolo26-plate | **AGPL-3.0** ⚠ [V] | YOLO26-pose, 4 keypoints, single/double + colour [V] | No (PyTorch/ONNX) |
| Chinese_license_plate_detection_recognition | https://github.com/we0091234/Chinese_license_plate_detection_recognition | **GPL-3.0** ⚠ [V] | yolov5, 12 plate types, double-layer [V] | No (PyTorch) |
| crnn_plate_recognition | https://github.com/we0091234/crnn_plate_recognition | **NO LICENSE** ⚠ [V] | CRNN recognizer [V] | No |
| **PlateRecognition** (pcb9382) | https://github.com/pcb9382/PlateRecognition | **MIT** [V] | C++; claims 99%+ **[T]**; CN/HK/Macau/TW/KR/US/EU [V] | **Claims** embedded/Android/**HarmonyOS**/iOS portability [V] — unverified |
| **OpenALPR** | https://github.com/openalpr/openalpr | **AGPL-3.0** ⚠ [V] | C++; last push 2024-01 [V] | Server/embedded Linux; CN support **[?]** |
| Ultralytics YOLO | https://github.com/ultralytics/ultralytics | **AGPL-3.0** ⚠ [V] | see §3 | Yes technically, **license-blocked** |
| rknn_model_zoo | https://github.com/airockchip/rknn_model_zoo | Apache-2.0 [V] | Rockchip NPU zoo; **LPR demo existence [?]** | Rockchip only |
| HyperLPR3 forks | LingZ6530/HyperLPR, ifunjoke/HyperLPR | forks of the above | — | — |

Star counts (fetched this session, **[V]**): HyperLPR 6,268 · LPRNet_Pytorch 1,159 · PaddleOCR 89,872 · CCPD 2,658 · CRPD 126 · CBLPRD-330k 258 · yolo26-plate 134 · Chinese_license_plate_… 1,876 · crnn_plate_recognition 420 · PlateRecognition 568 · OpenALPR 11,458 · Ultralytics 61,808 · rknn_model_zoo 2,768 · hyperlpr3-android-sdk 46.

**Dataset note:** `yuanwang688/CCPD` is a *fork* for a CS230 project; the canonical repo is **detectRecog/CCPD** (MIT). The fork's README reproduces the original dataset docs **[V]**.

---

## 1. Open-source projects — detail

### HyperLPR3 — the closest thing to a drop-in
Verified from its README **[V]**:
- **Licence Apache-2.0** (GitHub API license field).
- **Performance:** "720p faster, single core Intel 2.2G CPU (MacBook Pro 2015) average recognition time is less than 100ms"; accuracy "about 95%-97%" for entrance/exit scenes **[T]**.
- **Cross-platform:** Linux x86/Armv7/Armv8, macOS x86, **Android arm64-v8a + armeabi-v7a**; embedded **Rockchip rv1109/rv1126 (RKNPU)**.
- **Runtime:** C++ build needs **OpenCV ≥4.0 + MNN ≥2.0**; Python build uses **onnxruntime**. NDK 21 recommended.
- **Android integration:** JitPack dependency + `HyperLPR3.getInstance().plateRecognition(bitmap, …)`.
- **Plate types [V]** — *supported:* 单行蓝牌, 单行黄牌, 新能源车牌, 教练车牌. *Limited:* 白色警用, 使馆/港澳, 双层黄牌, 武警. *Not supported:* 民航, 双层武警, 双层军牌, **双层农用车牌**, 双层个性化.
- **Self-declared TODOs [V]:** multi-plate + **double-layer**, **large-angle** plates, and a **lightweight recognition model** — i.e. the authors themselves flag these as unfinished.
- **Training data/code:** plate data withheld for privacy/legal reasons; HyperLPR3 training code "will be sorted out later" — so **you cannot retrain HyperLPR3 as-is** **[V]**.

### LPRNet
From the paper text **[V]**:
- Input **94×24 RGB**; fully convolutional, **no RNN** (1×13 wide conv replaces LSTM), CTC loss, greedy or beam search decoding.
- **Accuracy / cost:** baseline 94.1% @ 0.71 GFLOPs; **basic 95.0% @ 0.34 GFLOPs**; reduced 94.0% @ **0.163 GFLOPs** (Chinese plates, private set of 11,696 crops).
- **Speed:** 3 ms/plate GTX 1080; **1.3 ms/plate** on i7-6700K via OpenVINO; 4 ms CPU+FPGA.
- **Post-filtering matters:** template-based post-filter + beam search adds **0.4–0.6%**; STN alignment adds 2.8–5.2%; global context is the single biggest gain (~36%).
- **⚠ Correction to the task brief:** the paper reports **GFLOPs, not parameter count**. The commonly quoted "LPRNet ≈1.7 M params" is **not stated in the paper** and I could not verify it **[?]**.

### PaddleOCR / PP-OCR
- Repo Apache-2.0 **[V]**. Official model sizes and accuracies, read from the PaddleOCR docs model tables **[V]**:

| Model | Avg Acc (%) | Storage | Notes |
|---|---|---|---|
| PP-OCRv5_server_rec | 86.38 | 81 M | CN/EN/TC/JA, handwriting, vertical |
| **PP-OCRv5_mobile_rec** | **81.29** | **16 M** | the mobile pick |
| PP-OCRv4_mobile_rec | 78.74 | 10.6 M | |
| PP-OCRv4_server_rec | 80.61 | 71.2 M | |
| PP-OCRv3_mobile_rec | 72.96 | 9.2 M | |
| ch_RepSVTR_rec | 65.07 | 22.1 M | mobile SVTR |
| ch_SVTRv2_rec | 68.81 | 73.9 M | server |

- **There is no first-class "license plate" model in PaddleOCR's model list.** The supported route is to **fine-tune a generic rec model on plate crops** — PaddleX documents a "license plate recognition tutorial" doing exactly that **[V]**. So "use PaddleOCR for plates" means "fine-tune `PP-OCRv4/v5_mobile_rec` on CCPD/CRPD crops", not "download a plate model".
- The docs have since moved on to **PP-OCRv6** (present in the current nav) **[V]**; the v3.0.2 page I read lists v5/v4/v3. Verify the current default before committing.
- PaddleOCR ships official **Android and iOS deployment** docs **[V]**. HarmonyOS is not listed.

### YOLO-based plate detectors
- `we0091234/yolo26-plate` **[V]**: AGPL-3.0; **pose** task emitting box + **4 corner keypoints**; classes `0: single`, `1: double`; pipeline = detect → **perspective transform on the 4 corners** → double-layer stitch → recognise text + **colour**; ONNX export output `1x300x14` (already NMS'd). This is a clean, modern reference for the geometry half of the pipeline — but it bundles Ultralytics source, so it is AGPL.
- `we0091234/Chinese_license_plate_detection_recognition` **[V]**: **GPL-3.0**, 1,876 stars, yolov5-based, claims 12 Chinese plate types + double-layer.
- `we0091234/crnn_plate_recognition` **[V]**: **no license file** → all rights reserved by default.
- **⚠ The license-laundering trap:** a third-party repo's own license does **not** neutralise Ultralytics' AGPL if it ships weights trained with Ultralytics code. Ultralytics explicitly claims control over *"custom-trained or fine-tuned YOLO models"* **[V]**.

### OpenALPR / commercial
- `openalpr/openalpr` is **AGPL-3.0** **[V]**, 11,458 stars, last pushed 2024-01 **[V]**. Closed-source commercial use requires a paid licence from the vendor (OpenALPR/Rekor). **Whether it supports Chinese plates is unverified this session [?]** — its historical focus is US/EU plates.
- Commercial Chinese vendors (Baidu, Tencent, Huawei Cloud OCR, Hikvision etc.) are mostly **cloud REST APIs** — unsuitable for offline on-device use, and the Huawei cloud AI Kit PDF I saw describes document/vehicle-licence OCR, not an on-device plate model **[T]**.

---

## 2. Datasets and the real hard cases

### Datasets (sizes verified)

| Dataset | Images | Annotations | Licence | Perspective | Illumination |
|---|---|---|---|---|---|
| **CCPD2019** | **355,013** [V] | plate text + bbox + **4 vertices** [V] | MIT [V] | yes [V] | yes [V] |
| **CCPD2020** | **11,776** [V] | same; **new-energy (green)** plates [V] | MIT | no [V] | no [V] |
| **CRPD** | ~30k (25k/6.25k/2.3k train/val/test) [V] | text + 4 vertices + type [V] | **none** ⚠ [V] | yes | yes |
| **CBLPRD-330k** | 330,000 [V] | text + bbox | MIT [V] | **no** [V] | **no** [V] |
| UFPR-ALPR / RodoSol / AOLP | 4,500 / 20,000 / 2,049 [V] | — | — | no | no |

- **CCPD annotation format** is encoded in the *filename*: `<area>-<tilt>-<bbox>-<vertices>-<plate_no>-<brightness>-<blurriness>.jpg`, with `plate_no` as space-separated **character indices** **[V]**. Sub-datasets named in the README: `blur / challenge / db / fn / np / rotate / tilt` **[V]**.
- **CCPD character set [V]:** 34 provinces (incl. 警, 学 and a null `O`), 25 letters (no `I`/`O`), 35 position-3+ symbols (no `I`/`O`). Note **`I` and `O` never appear on a Chinese plate** — `O` is the "no character" padding symbol. This is a free, high-value post-processing constraint.
- **CCPD's structural weaknesses [V]:** exactly **one plate per image** (224,001 images with 1 LP, 0 with ≥2, per CRPD's comparison table) and **no character-level annotations**. CRPD also notes CCPD is captured in **parking lots**, so it lacks running/turning/far-away vehicles.
- **CRPD's added value [V]:** multi-object images (6,242 with 2 LPs, 1,232 with 3, 371 with ≥4), running/turning/far-away vehicles, and special vehicles (coaches, police, trailers). **Its code was never released** ("will be available after the paper is published") and there is **no LICENSE file** — flag both.

### Plate standards and how many classes a production system needs

Verified type taxonomies found:

- **CRPD** uses **4 types**: `0` blue (small cars), `1` yellow single-line (front of large vehicles), `2` yellow double-line (rear of large vehicles), `3` white (police) **[V]**.
- **HyperLPR3** supports ~8 labels (4 full + 4 partial) and explicitly *cannot* do 民航, 双层武警, 双层军牌, 双层农用车牌, 双层个性化 **[V]**.
- **A shipping commercial plugin** returns **6** types on HarmonyOS vs **10** on Android/iOS **[T]** — a concrete measure of the HarmonyOS capability gap.

**Synthesis (my judgement, not a sourced claim):** detection itself needs only **1–2 classes** (plate / single-vs-double layer); colour and type are better derived from a colour-analysis branch or a small classifier. A *production* type label set realistically needs **~8–13**: 蓝牌, 黄牌单层, 黄牌双层, 新能源(绿牌, small + large), 白牌(警/军), 黑牌(港澳/使馆), 教练, 挂车, 农用车, 使领馆, 警用. The recognizer charset needs roughly **65–70 symbols**: 31 province abbreviations + A–Z minus I/O + 0–9 + specials (警 学 挂 领 使 港 澳 试 超 临).

### Real hard cases
Evidence-backed list (the *frequencies* come from BLPR's street census **[V]**, which is the only hard-case frequency data I found):

1. **Skew / large viewing angle — the dominant failure mode.** BLPR counted **2,867 skewed** plates in 3,548 street images, "substantially exceeding all other categories" **[V]**. HyperLPR3 lists large-angle support as an open TODO **[V]**, and CRPD added rotated-bbox regression + RRoIAlign specifically for tilt **[V]**.
2. **Low illumination / glare** — 570 low-illumination instances in BLPR **[V]**; night + headlight glare + weather in CRPD **[V]**.
3. **Motion blur** — 860 blurred in BLPR **[V]**; CRPD captures running vehicles **[V]**. BLPR argues blur "may require fundamentally different solutions (e.g. faster shutter speeds)" **[V]**.
4. **Double-layer (双层) plates** — yellow double-line rear plates of large vehicles. Explicitly unsupported/limited in HyperLPR3 **[V]**; needs a stitch step (yolo26-plate does exactly this) **[V]**.
5. **New-energy green plates (8 characters, D/F position)** — a different length and grammar; CCPD2020 exists specifically for this **[V]**. Shipping plugins validate "新能源 D/F 位" explicitly **[T]**.
6. **Special plates:** 警/军/武警, 使馆, 港澳两地牌, 农用车, 教练, 挂车, 民航. HyperLPR3 admits "some special license plates have low recognition rates, such as (Embassy/Hong Kong and Macao)" due to class imbalance **[V]**.
7. **Multi-plate scenes** — CCPD has none; CRPD was built to fill this **[V]**.
8. **Small / far-away plates** — CRPD explicitly covers "far away" **[V]**; models trained on CCPD's large plates transfer poorly to small ones (CRPD observed exactly this transfer drop) **[V]**.
9. **Character confusion** — `O`/`0`, `I`/`1`, `8`/`B`, `2`/`Z`, `5`/`S`. Chinese plates *structurally exclude* `I` and `O` **[V]**, so these are correctable by rule — see §5.

---

## 3. Model sizes, compute budgets, quantization, and the latency evidence gap

### Budgets

| Model | Params | GFLOPs | Input | Source |
|---|---|---|---|---|
| YOLOv8n | ~3.2 M **[?]** | ~8.7 @640 **[?]** | 640 | *widely cited; NOT re-verified this session* |
| LPRNet basic | **[?]** | **0.34** [V] | **94×24** [V] | paper |
| LPRNet reduced | **[?]** | **0.163** [V] | 94×24 [V] | paper |
| PP-OCRv5_mobile_rec | — | — | — | **16 M storage** [V] |
| PP-OCRv4_mobile_rec | — | — | — | **10.6 M storage** [V] |

**⚠ I could not verify the YOLOv8n parameter/GFLOP figures** (the searches for the Ultralytics model table failed). The task brief's "~3 M / ~8.7 GFLOPs" is consistent with common knowledge but is marked unconfirmed here. Do not quote it as sourced.

**The asymmetry that matters:** the recognizer is ~25× cheaper than the detector (0.34 vs ~8.7 GFLOPs). On a tight NPU budget, spend it on the detector, and keep the recognizer tiny.

### Quantization
- **Typical practice:** INT8 post-training quantization (PTQ) for both stages; detector at **320/416/640** input, recognizer at **94×24** (LPRNet) or **96×32 / 48×168** variants.
- **Accuracy drop from INT8 PTQ: I could not verify a number [?].** No credible LPR-specific PTQ study surfaced in the searches that succeeded. This is a genuine evidence gap — plan to measure it yourself on your own validation split.
- MindSpore Lite's INT8 support and HarmonyOS NNRT/NPU specifics: **unverified [?]** (vendor pages returned no readable body).

### Mobile NPU latency — **the weakest evidence in this whole survey**
- **I found no verified ms/frame figure for a Chinese LPR detect+recognize pipeline on Hexagon, MediaTek APU, or Huawei Da Vinci.** Searches for it failed.
- What I *can* honestly report:
  - LPRNet **alone**: 1.3 ms on a desktop i7 CPU (OpenVINO), 3 ms on a GTX 1080 **[V]** — this is the recognizer only, and it is desktop silicon.
  - HyperLPR3: **<100 ms per 720p frame on a single 2.2 GHz Haswell CPU core** **[T]** — end-to-end, but a 2015 laptop, not an NPU.
  - CRPD's baseline claims **30 fps at 640p** **[V]** — but that was measured on an **NVIDIA TITAN RTX** **[V]**. Quoting it as a mobile number would be misleading.
  - A shipping plugin's doc shows `totalMs: 386` for one plate recognition **[T]** — but this is an *example value in a README*, not a benchmark, and the device is unspecified. Treat as illustrative only.
- **Practical guidance (my judgement):** assume a well-quantized 640-input detector + 94×24 recognizer lands in the **tens of milliseconds** per frame on a modern flagship NPU, but **treat this as an estimate to be measured, not a sourced fact.** Budget for 15–30 FPS camera preview and do detection every Nth frame with tracking in between (§4).

---

## 4. Pipeline architecture in practice

The four-stage pipeline is consistent across every real implementation I read:

```
frame → [1] detect (bbox + 4 corners) → [2] perspective/plate correction
      → [3] recognize (CTC) → [4] post-process (rules) → result
```

**[1] Detection.** Either a plain bbox detector, or — better — a **keypoint/pose** head giving the **4 plate corners** directly. `yolo26-plate` does exactly this, emitting box + 4 corner keypoints with classes `single`/`double` **[V]**. CRPD's baseline instead regresses **rotated** bounding boxes `(x, y, w, h, θ)` and crops features with **RRoIAlign**, which measurably beat RoIPool/RoIAlign (F 89.4 vs 87.0/87.2) **[V]** — i.e. *handling rotation properly is worth ~2 F-score points.*

**[2] Perspective correction (四点透视变换).** Use the 4 corners for a homography to a canonical crop. The shipping plugin returns a corrected plate image of **400×120** **[T]** — a sensible canonical size to standardise on. Also apply **photometric correction**; BLPR formalises the stage as `y = f_OCR(f_photo(f_rect(R)))` **[V]** and finds illumination handling matters.

**[3] Recognition.** CTC-based, segmentation-free (LPRNet, CRNN, or a fine-tuned PP-OCR rec). Prefer **greedy + beam search**; LPRNet's own ablation shows beam search + template post-filtering adds 0.4–0.6% **[V]**.

**[4] Post-processing — this is where cheap accuracy lives.** Verified from shipping implementations:
- **Province-abbreviation + structure regex.** A real plugin exposes `plateCheckedValid` = "省简称 + 发牌字母 + 尾段结构，含新能源 D/F 位与尾字牌" and `plateCharsetValid` = "字母不含 I/O" **[T]**. Reimplement both — they are pure logic and cost nothing.
- **Colour discrimination (颜色判别)** as a separate small classifier/branch — yolo26-plate recognises plate colour alongside text **[V]**; CRPD's type label is effectively colour+layout **[V]**.
- **Character-confusion fixes** using the plate grammar (no `I`/`O` on Chinese plates **[V]**).

**Double-layer (双层) handling.** Detect `single` vs `double` as a class (yolo26-plate does) **[V]**, then **stitch the two halves into one wide strip** before recognition **[V]**. HyperLPR3 cannot do this **[V]** — so this is a genuine differentiator if your scenes include trucks/buses.

**Multi-frame tracking / voting for video.** Two directly relevant papers surfaced (titles/venues verified, contents not read) **[V]**:
- *"Quality-Aware Frame Selection and Two-Tier Voting for Video-Based Licence Plate Recognition under Adverse Conditions"* — https://journal.uob.edu.bh/bitstreams/fc1a8e17-cea4-43bb-8f62-b297b3fca9f9/download
- *"Geometry-Constrained Multi-Frame Character Association for License Plate Recognition on Moving Cameras"* — MDPI Sensors 26(18):5704, https://www.mdpi.com/1424-8220/26/18/5704

The standard design (corroborated by the above being framed as "frame selection + voting" and "multi-frame character association"): **detect every Nth frame → track the plate across frames → recognise per frame → per-character confidence-weighted vote across the track.** LPRNet's own post-filtering (beam search over a template set) is the single-frame analogue **[V]**. This is the highest-value addition for video and it is cheap.

---

## 5. Where a VLM/LLM actually helps — and where it hurts

### The honest answer: it helps only as an off-device, confidence-gated fallback. On-device, it loses.

**The decisive paper** — *BLPR: Robust License Plate Recognition under Viewpoint and Illumination Variations via Confidence-Driven VLM Fallback* (arXiv **2604.09927**), https://arxiv.org/abs/2604.09927 **[V]**:
- Architecture: YOLO detector (Blender-synthetic pretrain → real fine-tune) → geometric rectification → photometric correction → character recogniser, with **Gemma3 4B as a *selectively triggered* fallback** for low-confidence reads, constrained by plate syntax.
- Result: **89.6% character-level accuracy** on real-world data.
- Trigger rule (concrete and reusable): fall back when **`length < 6`** or **`min_conf < 0.20 × max(conf)`** **[V]**.
- **Its own conclusion on VLMs [V]:** VLMs "remain constrained by high computational cost and latency, requiring substantially more inference time and resources than dedicated OCR or LPDR pipelines, thereby limiting their deployability in real-time, resource-constrained environments… **they are not yet viable substitutes for specialized recognition systems in practical deployments.**"
- It also notes VLMs work as a "semantic consistency layer that **complements, rather than replaces**, visual recognition models", citing **CLOCR-C** for LLM-based contextual post-correction reducing character error rates **[V]**.

**The pro-VLM paper** — *Evaluating Vision-Language Models as a Zero-Shot Learning Alternative to YOLO and OCR for **Nigerian** License Plate Recognition* (arXiv **2607.02025**), https://arxiv.org/abs/2607.02025 **[V]**:
- Evaluated Gemini 2.0 Flash Exp, Qwen2.5-VL-7B-Instruct, GPT-4o, Claude 4 Sonnet, Llama 3.2 Vision 90b on **88 challenging real-world images**, CER metric. Gemini and Qwen outperformed.
- **Read the caveats before believing it:** n = **88 images**, **zero-shot**, and every model is either a cloud API or **7B–90B** parameters. This is *not* evidence that a VLM beats a CNN on-device; it is evidence that large cloud VLMs can beat a *poorly-tuned* YOLO+OCR baseline on a tiny hard set. I read only the abstract, not the numeric table **[V]**.

**Other VLM-for-plates work found (titles verified, contents not read) [V]:**
- *VIDEO-BASED VEHICLE SURVEILLANCE IN THE WILD: LICENSE PLATE, MAKE, AND MODEL RECOGNITION WITH SELF REFLECTIVE VISION-LANGUAGE MODEL* — arXiv 2508.01387
- *Advancing Vehicle Plate Recognition: Multitasking Visual Language Models with **VehiclePaliGemma*** — https://islab.ulsan.ac.kr/files/announcement/893/pp.pdf

### Verdict table

| Where | Verdict | Evidence |
|---|---|---|
| Clean, well-lit, standard plates | **VLM is worse** — slower, bigger, no accuracy gain | BLPR [V] |
| On-device (HarmonyOS phone) | **VLM is not viable** — 4B+ model, latency/thermal prohibitive | BLPR explicitly [V] |
| Hard cases (blur, skew, glare, unusual layout) | **VLM can help** — but only as a server-side fallback | BLPR, Nigerian paper [V] |
| **LLM as post-processing corrector** | **Best value for LLM** — cheap, and CLOCR-C shows CER reduction | BLPR citing CLOCR-C [V] |

**Concrete recommendation:** do **not** ship a VLM. If you want the hard-case win, implement the **BLPR trigger** (`length<6` or `min_conf < 0.2·max_conf`) to *route the crop to a server* and keep the device pipeline CNN-only. And implement the **rule-based corrector on-device** (§4) — that captures most of the "LLM post-correction" benefit at zero compute.

**Where evidence is thin:** I found **no** study that runs a VLM *on a phone* for plates and reports latency. The on-device infeasibility is inferred from model size (4B–90B) and BLPR's stated conclusion, not from a measured on-device VLM benchmark.

---

## 6. HarmonyOS specifics

### Official SDK: general OCR only, no plate API
- The official on-device text API is **Core Vision Kit `textRecognition`** (ArkTS): https://developer.huawei.com/consumer/cn/doc/harmonyos-references/core-vision-text-recognition-api
  - **⚠ I fetched this URL and the body was empty ("文档中心") — it is JS-rendered.** I verified the URL and title from search results but **could not read the API contract [?]**. Read it yourself before designing against it.
- Corroborating third-party evidence that it is *general* text recognition, not plates:
  - A Huawei developer-forum thread titled *"textRecognition 识别图片文字老是空白或漏字,旋转图片还识别错"* — i.e. quality complaints on a generic recogniser **[T]**.
  - A Huawei forum thread asking *"HarmonyOS 有图像识别的第三方库"* and one on *"如何在鸿蒙中实现离线 AI 推理（如图像识别）？有官方 AI 框架吗？"* — both signal the absence of a turnkey vision API **[T]**.
- **Huawei AI Kit / cloud OCR** exists but is a **cloud REST service** (the API PDF lists 证件类 endpoints such as 行驶证识别 and notes "只支持中国大陆行驶证的识别") **[T]** — not an offline on-device plate model.

### The one shipping three-platform implementation (and what it reveals)
The `xwq-ocr` DCloud plugin is the most informative single artifact I found **[T]** — https://ext.dcloud.net.cn/plugin?id=29660. Its own documentation states the engines per platform:

| Capability | Android | iOS | **HarmonyOS** |
|---|---|---|---|
| Plate recognition | **HyperLPR3** | **HyperLPR3** | **系统 OCR + 车牌规则** (system OCR + plate rules) |
| VIN recognition | ML Kit | Vision | **CoreVisionKit** |
| Needs model files | No (HyperLPR3 bundled) | **Yes — 6 × `.mnn`** | No |
| Offline | Yes | Yes | Yes |
| Plate type labels returned | 10 types | 10 types | **6 types** (蓝牌/黄牌/新能源/港澳/警用/使领馆) |

**Conclusions this licenses:**
1. On HarmonyOS, **no open-source plate model is being used at all** — the vendor falls back to system OCR + regex. If a commercial vendor with a ¥600 source licence does this, there is **no off-the-shelf HarmonyOS plate model**.
2. iOS bundles **MNN** models (6 × `.mnn`) — i.e. **MNN is the proven cross-platform runtime for HyperLPR3**, and MNN's HarmonyOS/OpenHarmony support is the natural porting path to investigate **[T]**.
3. The HarmonyOS camera preview is a **known risk**: it needs ArkTS pages (`VinScannerPage.ets`, `PlateScannerPage.ets`, `main_pages.json`) placed in the *project's* `harmony-configs/…`, which **cannot ship inside a plugin** — the vendor tells buyers to contact the author for the files **[T]**. Expect to write ArkTS camera/overlay code yourself.
4. Practical HarmonyOS notes from that doc: use `ohos.permission.CAMERA`; photo album via `PhotoViewPicker`; Android capture locked to 16:9 (1280×720 / 1920×1080) because non-16:9 breaks plate detection **[T]**.

### The other plugin — and a direct warning
`ad-lpr-ocr` **[T]** — https://ext.dcloud.net.cn/plugin?id=29278:
- **19 MB** plugin, **¥50** commercial licence, local/offline ("纯本地推理…不采集、不上传任何数据"), returns `plateText`, `plateType`, `confidence`, `totalMs`, and a **400×120 corrected plate image**; error codes include `9010002 模型缺失`.
- **Platform table: Android 7.0+ ✓, iOS 15+ ✓, 鸿蒙 ✗ — HarmonyOS is explicitly NOT supported.** Also no 鸿蒙元服务, no mini-programs.
- **So: not a cloud API (it is genuinely local), but it is Android/iOS-only and closed/paid.** Neither plugin is open source; both are commercial DCloud marketplace products.

### Runtime / NPU porting — mostly unverified
- **MindSpore Lite** is Huawei's on-device inference framework and the natural HarmonyOS path, but I **could not verify** this session: whether it imports ONNX directly, what NNRT/NPU acceleration it exposes, or its INT8 quantization docs **[?]**. Verify at the official HarmonyOS docs before committing.
- **MNN** is the runtime with actual evidence behind it here: HyperLPR3's C++ build requires MNN ≥2.0 **[V]** and the iOS plugin ships `.mnn` models **[T]**. **Porting MNN to HarmonyOS/OpenHarmony is the most concrete, evidence-backed route** — it is also what HyperLPR3's Android SDK already does.
- **rknn_model_zoo** (Apache-2.0 **[V]**) is the Rockchip NPU reference and HyperLPR3 claims RKNPU support **[V]** — useful as an INT8/NPU porting reference, though I could not confirm an LPR demo inside it **[?]**.

---

## 7. Licensing traps — read this before shipping

| Trap | Licence | Practical consequence |
|---|---|---|
| **Ultralytics YOLO (v5/v8/v11/v26)** | **AGPL-3.0** [V] | The vendor's own page states an Enterprise Licence is required for *"Any commercial product or service"*, *"Proprietary / closed-source software"*, *"Embedded deployments in hardware, edge devices, robotics, cameras, or appliances"*, and *"Using custom-trained or fine-tuned YOLO models in a proprietary or commercial setting"* **[V]**. **A closed-source HarmonyOS app is in this list.** AGPL also means open-sourcing *your entire app* if you distribute it. |
| **OpenALPR** | **AGPL-3.0** [V] | Same network-copyleft exposure; commercial use needs a paid vendor licence. |
| `we0091234/yolo26-plate` | **AGPL-3.0** [V] | Inherits Ultralytics AGPL; it vendors Ultralytics source. |
| `we0091234/Chinese_license_plate_detection_recognition` | **GPL-3.0** [V] | Copyleft — distributing the app obliges you to release source. |
| `we0091234/crnn_plate_recognition` | **no LICENSE file** [V] | ⚠ **All rights reserved by default.** No licence = no grant of rights. Do not ship. |
| **CRPD** | **no LICENSE file** [V] | ⚠ Dataset is downloadable but **unlicensed**; paper/README say code arrives "after the paper is published" — it never did. Legally risky to train on and redistribute. |
| **CCPD / CBLPRD-330k** | MIT [V] | Clean. Attribute and include the MIT notice. |
| **HyperLPR3** | **Apache-2.0** [V] | Clean and commercial-friendly. **But** the *plate training data* is withheld for privacy/legal reasons **[V]** — so you inherit a model you cannot retrain. |
| **PaddleOCR** | Apache-2.0 [V] | Clean. Check third-party model/dataset provenance for anything you fine-tune on. |
| **LPRNet_Pytorch / PlateRecognition** | Apache-2.0 / MIT [V] | Clean. |
| DCloud plugins (`ad-lpr-ocr`, `xwq-ocr`) | **commercial, closed** [T] | ¥50 / ¥99 (¥600 for source). Not open source; a per-plugin licence, and HarmonyOS live-preview needs extra vendor-supplied files. |

**Bottom line for a closed-source HarmonyOS product:** avoid Ultralytics entirely, or buy the Enterprise Licence. Prefer **HyperLPR3 (Apache-2.0) + LPRNet (Apache-2.0) + CCPD (MIT) + CBLPRD-330k (MIT)**. If you train your own detector, train it with a permissive framework and do not initialise from Ultralytics weights.

---

## 8. Where evidence is thin or missing (explicit)

1. **No verified mobile-NPU latency for any Chinese LPR pipeline.** All readable numbers are desktop CPU/GPU or illustrative doc values. **This is the single biggest gap.**
2. **YOLOv8n params/GFLOPs not re-verified** — searches failed; treat "~3 M / ~8.7 GFLOPs @640" as unconfirmed.
3. **LPRNet's "~1.7 M params" is not in the paper** — the paper reports GFLOPs only. The figure may be right but is unsourced here.
4. **INT8 PTQ accuracy drop for plate detection/recognition: no data found.** Measure it yourself.
5. **HyperLPR3 model size in MB: not stated in its README.** Only a model-directory name (`r2_mobile`) is visible.
6. **Core Vision Kit `textRecognition` API contract: unread** (JS-rendered page). URL verified, contents not.
7. **MindSpore Lite on HarmonyOS:** ONNX import, NNRT/NPU acceleration, and INT8 docs **unverified**.
8. **OpenALPR's Chinese-plate support: unverified.** Its focus is historically US/EU.
9. **PaddleDetection plate models: not checked** (search quota exhausted).
10. **`rknn_model_zoo` LPR demo existence: unverified** (a `sophgo/sophpi-shaolin` LPRNet example appeared in results but I did not read it).
11. **The two video-LPR papers were verified by title/venue only**, not by reading their methods or numbers.
12. **BLPR's 89.6% is on Bolivian plates**, not Chinese — the *architecture* (confidence-gated VLM fallback) transfers, the accuracy number does not.
13. **The Nigerian VLM paper is n=88, zero-shot, cloud/7B–90B models** — weak evidence for anything on-device.
14. **Search tooling failed partway through** (HTTP 402, insufficient balance on the search endpoint). Several planned queries — notably mobile NPU benchmarks and OpenALPR Chinese support — never ran. Re-run those before finalising hardware assumptions.

---

## 9. Source list

**Repos / licences (GitHub REST API, read this session):**
- https://github.com/szad670401/HyperLPR · https://github.com/HyperInspire/hyperlpr3-android-sdk
- https://github.com/sirius-ai/LPRNet_Pytorch
- https://github.com/PaddlePaddle/PaddleOCR
- https://github.com/detectRecog/CCPD · https://github.com/yxgong0/CRPD · https://github.com/SunlifeV/CBLPRD-330k
- https://github.com/we0091234/yolo26-plate · https://github.com/we0091234/Chinese_license_plate_detection_recognition · https://github.com/we0091234/crnn_plate_recognition
- https://github.com/pcb9382/PlateRecognition
- https://github.com/openalpr/openalpr · https://github.com/ultralytics/ultralytics · https://github.com/airockchip/rknn_model_zoo

**Papers:**
- LPRNet — https://arxiv.org/abs/1806.10447
- CRPD / Unified Chinese LP Detection and Recognition — https://arxiv.org/abs/2205.03582 (JVCIR 2022)
- BLPR (VLM fallback) — https://arxiv.org/abs/2604.09927
- Nigerian VLM vs YOLO+OCR — https://arxiv.org/abs/2607.02025
- Self-reflective VLM vehicle surveillance — https://arxiv.org/abs/2508.01387
- Video LPR frame selection + two-tier voting — https://journal.uob.edu.bh/bitstreams/fc1a8e17-cea4-43bb-8f62-b297b3fca9f9/download
- Multi-frame character association (MDPI Sensors 26(18):5704) — https://www.mdpi.com/1424-8220/26/18/5704
- VehiclePaliGemma — https://islab.ulsan.ac.kr/files/announcement/893/pp.pdf

**Vendor / platform docs:**
- Ultralytics licence (AGPL terms) — https://www.ultralytics.com/license
- PaddleOCR text recognition model table — http://www.paddleocr.ai/v3.0.2/version3.x/module_usage/text_recognition.html
- HarmonyOS Core Vision Kit `textRecognition` — https://developer.huawei.com/consumer/cn/doc/harmonyos-references/core-vision-text-recognition-api
- DCloud `ad-lpr-ocr` — https://ext.dcloud.net.cn/plugin?id=29278
- DCloud `xwq-ocr` — https://ext.dcloud.net.cn/plugin?id=29660
