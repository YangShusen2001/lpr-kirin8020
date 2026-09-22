# Landing Self-Evidencing on a Domestic-Process Mobile NPU

**A Chinese licence-plate recognition pipeline on Kirin 8020 — built as a measurement
instrument, not just an app.**

[English](README.md) | [中文](README.zh-CN.md)

---

## The problem this repository exists to answer

On HarmonyOS, one question about a deployed model cannot be answered by measurement:

> Did the work actually run on the NPU?

NPU utilisation is not exposed to applications, not available through the on-device
debug shell, and has no vendor profiling template. The only NPU-related counter
available is a *temperature*. Meanwhile placement is silent — a model requested on the
NPU may be served by the CPU with no error code — and a model that *does* land on the
NPU may compute a different answer than its CPU counterpart, also without an error code.

So this project treats it as a measurement problem. Every inference records the
requested backend, the observed backend, and any fallback transition:

```
req=nnrt   LANDED=NNRT:NPU_ohos.boot.hardware.kirin8020_v2_0   fallback=
fingerprint  l2=4.0489
```

Placement is therefore **read from raw logs** rather than asserted from a configuration
file. A configuration file describes intent; it is not evidence about execution.

## Three findings

**1 · The protocol works — including by catching us over-claiming it.**
It detected a pure pre-processing defect that was invisible at the output layer: a
padding region was not being zeroed, so residue from a previous, differently-laid-out
run leaked into the recogniser's input. The output symptom was a plausible-looking plate
string missing one character. The tensor fingerprint faithfully recorded that something
had changed — and only aligning the session timeline showed the change was on our side,
not the accelerator's. We had initially claimed the fingerprint proved *placement*; on
measurement that claim was false (all models declare FP32 outputs, so the fp16 re-read is
garbage on every backend), and the protocol was rewritten. See
[`docs/adr/0003`](docs/adr/0003-evidence-standard-latency-delta-and-landing.md).

**2 · Operator support is a model × toolchain property, not a hardware property.**
On the NNRT path, 16 of 36 single-operator probes are rejected when compiled standalone —
including `ReLU`, `Sigmoid`, `Softmax`, `MaxPool`, `Pad`, `Cast`, `Transpose`, `Resize`.
Taken at face value, that says the accelerator cannot execute a rectifier. On the CANN
path, 51/51 probes pass every gate, including all nine operators the NNRT path rejects.
`ConvTranspose` cannot be *converted at all* on the NNRT side, and converts and runs on
the CANN side. The same ONNX file fails to produce a model on one path and runs on the
other.

**3 · Which knob actually matters.**
Over 1,000 real vehicle images, switching the recogniser's backend changed **no** output
and the detector's **one**. That is the result one wants — and it is also the result
easiest to over-read. A *paired* McNemar test shows the backend **is** an accuracy
variable (+3.2 pp, p < 0.0001), and that **plate length costs an order of magnitude
more** (−6.6 pp). The practical conclusion: effort spent re-validating outputs after a
backend switch is largely misdirected; effort spent on plate-type and province coverage
is not.

## Headline numbers

Every figure below is recomputed from raw evidence by
[`tools/verify_published_numbers.py`](https://github.com/YangShusen2001/lpr-kirin8020-app/blob/main/tools/verify_published_numbers.py),
which fails if a declared value no longer matches its source. See
[`docs/evidence-index.md`](docs/evidence-index.md) for the full table and provenance.

| Quantity | Value | Conditions | Evidence |
|---|---|---|---|
| Recogniser output changed by switching backend | **0 %** (0/1000) | real vehicle scenes, n=1000 | `ccpd_scene_rec.log` |
| Detector output changed by switching backend | **0.1 %** (1/1000) | same images, same probe | `ccpd_scene.log` |
| Recogniser, NPU vs CPU (same stack) | **4.46×** | 16.78 ms vs 3.76 ms, n=961/993 | `crop_bare.log` |
| Backend effect on accuracy | **+3.2 pp**, p < 0.0001 | paired McNemar, 38:6 | `mcnemar_triplet.py` |
| Device NPU vs host reference | **−0.7 pp**, p = 0.0156 | paired, strictly nested 0:7 | `mcnemar_device_vs_host.py` |
| Full pipeline, real scenes | **99.1 %** | 7-character plates, n=1000 | `ccpd_scene.log` |
| 8-character new-energy plates | **92.5 %** | n=1000, 60 % Anhui (skew unavoidable) | `scene_green_rec.log` |
| Plate-length cost | **−6.6 pp** | province-matched control | T13 |
| Province share of substitution errors | **49.3 %** (33/67) | equal-length rows, n=971 | `scene_green_rec.log` |
| CANN operator admission | **51/51** | incl. 9 rejected by NNRT | `op_collide.csv` |
| Frame budget: detection vs recognition | **49 % / 10 %** | production config, detected frame | `camera_summary.md` |
| Isolated probe vs in-pipeline cost | **7.4 ms vs 19.5–31.6 ms** | same model, backend, thread count | `camera_gap_sweep.log` |
| Latency drift under sustained load | **+26.9 %** | 23.3 min / 80 rounds, thermal level **unchanged** | `rq4_thermal_80r.csv` |
| Thermal 2→3 crossing | **never reached** | 80/80 rounds at level 2 — a negative result | `rq4_thermal_80r.csv` |

## What we deliberately do NOT claim

This section is the point of the repository as much as the numbers are.

- **No NPU utilisation figure.** The platform does not expose one. Any such number would
  be unverifiable.
- **The tensor fingerprint proves a backend computed — not that it computed correctly.**
  Correctness is established only against human-annotated ground truth.
- **"Fusion carry-over" is a correlation, not a causal claim.** The mechanism proposed to
  explain why rejected operators still execute (they are carried as fusion neighbours of
  an adjacent convolution) requires a controlled experiment with fixed weights and varied
  operator isolation. That experiment has not been run.
- **No cross-stack speed-up is reported as a result.** NPU runs on MindSpore Lite, GPU
  only through ncnn-Vulkan, CPU on two different stacks. Only same-stack ratios are
  comparable; every table carries its framework.
- **No "GPU acceleration" claim.** Measured on Vulkan, all three models were *slower*
  than CPU; the honest statement is that the path works and is numerically faithful.
- **`arrive == done` does not mean the pipeline keeps up.** Under back-pressure the
  discarded frames are never delivered and therefore never counted as dropped. The
  distinction requires a control that acquires frames without inference.
- **Our own earlier conclusions are overturned twice in this repository** (T10 → T12,
  T11 → T14), and the corrections are kept rather than rewritten away. A repository that
  only contains confirmations is not evidence of care.

## Layout

```
docs/
  adr/            7 decision records — including three where we overturned ourselves
  notes/          19 raw experiment notes, corrections preserved in place
  spec.md         scope, user stories, out-of-scope
  evidence-index.md   every published number → the file it came from
paper/
  en/main.tex     IEEEtran conference manuscript
  figures/        generated from evidence by tools/make_figures.py
tools/
  scan_for_publication.py    pre-publication compliance scan
  sanitize_paths.py          replaces machine-specific path prefixes with placeholders
```

The application itself lives in a separate repository,
[`lpr-kirin8020-app`](https://github.com/YangShusen2001/lpr-kirin8020-app), because the
HarmonyOS build system rejects project paths containing non-ASCII characters, and this
documentation repository's path contains Chinese characters.

## Reproduce

```bash
# Verify every published number against the raw evidence
cd <REPO>/lpr-kirin8020-app
python tools/verify_published_numbers.py

# Regenerate the figures
python tools/make_figures.py --out <REPO>/lpr-kirin8020/paper/figures

# Build and install the app (release mode is mandatory for any timing figure —
# a debug build silently overrides -O3 with -O0 and inflates latency 1.7–4×)
bash build.sh assembleHap
```

Models are **not** in this repository. The three ONNX models are converted to `.ms` by
[`tools/convert_ms.sh`](https://github.com/YangShusen2001/lpr-kirin8020-app/blob/main/tools/convert_ms.sh);
the documented toolchain and the on-disk sources are recorded in
[`docs/notes/toolchain-and-sources-on-disk.md`](docs/notes/toolchain-and-sources-on-disk.md).

## Prior work

This repository inherits **data and conclusions** from two earlier projects, but not
their codebases ([ADR-0001](docs/adr/0001-inherit-prior-data-not-codebase.md)).
Numbers inherited from them are marked as such in
[`docs/evidence-index.md`](docs/evidence-index.md) §6 and are not counted as new results.

| Repository | Contribution |
|---|---|
| [shusen-npu-characterization](https://github.com/YangShusen2001/shusen-npu-characterization) | L1 operator matrix, L2 model suite, roofline, INT8 form conclusions, vendor ticket chain |
| [lpr-showcase](https://github.com/YangShusen2001/lpr-showcase) | Evidence layer: 1,000-image ground-truth set, raw probe logs, archived prior manuscript |
| [lpr-harmony](https://github.com/YangShusen2001/lpr-harmony) | Prior application source, used as the rewrite baseline |

## License and third-party assets

Code in this repository is provided for research and reference use. Third-party
components retain their own licences, and the models and datasets are **not**
redistributed here:

- **Inference stack** — MindSpore Lite Kit 2.6.0 NDK, NNRT delegate (Huawei).
- **Models** — public pre-trained weights; per-asset terms in the table below. We train
  nothing; every model is used as published.
- **Datasets** — CCPD / CCPD2020-Green (ECCV 2018) are used under their own terms and are
  **not** redistributed. Sampling scripts are included; the images are not.
- **CANN DDK / OMG** — anonymously downloadable from the vendor, not redistributed here.

### Per-asset licences

| Asset | Role | Upstream | Licence |
|---|---|---|---|
| `models/yolov5su_320_veh_fp32.ms` | Vehicle detection (ROI-path pre-stage) | ultralytics **YOLOv5u** COCO pre-trained weights (`yolov5su.pt`, ultralytics 8.4.117); DFL rewritten, then converted to MindSpore Lite | **AGPL-3.0** |
| `models/y5fu_320x_head*.ms` / `.ncnn.*` | Plate detection | project baseline, YOLOv5 architecture | per upstream |
| `models/rpv3_mdict_160_r3.*` | Plate recognition | project baseline | per upstream |
| `models/litemodel_cls_96x_r1.*` | Plate colour classification | project baseline | per upstream |
| `libs/arm64-v8a/libncnn.so` | GPU (Vulkan) inference runtime | [Tencent ncnn](https://github.com/Tencent/ncnn) | **BSD-3-Clause** |
| `libs/arm64-v8a/libomp.so` | OpenMP runtime (ncnn dependency) | [LLVM OpenMP](https://github.com/llvm/llvm-project) | **Apache-2.0 with LLVM Exceptions** |

> ⚠️ **AGPL-3.0 note.** `yolov5su_320_veh_fp32.ms` derives from ultralytics YOLOv5, which is
> AGPL-3.0. This repository does **not** redistribute that weight — obtain it upstream and
> convert it yourself. If you build a work containing an AGPL-3.0 component and distribute
> it or expose it over a network, the AGPL's obligations apply to **you**; assess them
> yourself. Vehicle detection is an **optional** pre-stage — the direct-detection path does
> not use it.
>
> `libncnn.so` / `libomp.so` are redistributed as prebuilt binaries; their copyright
> notices remain with their respective holders.

No NPU utilisation figure appears anywhere in this repository, by design.
