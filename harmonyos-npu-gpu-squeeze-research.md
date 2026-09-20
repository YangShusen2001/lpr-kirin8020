# 榨干 HarmonyOS NEXT / 6.x 的 NPU/CPU/GPU —— 第三方应用视角

Research note, 2026. Companion to [`on-device-chinese-lpr-survey.md`](on-device-chinese-lpr-survey.md), which flagged MindSpore Lite / NNRt / NPU specifics as **unverified [?]**. This note closes that gap.

**Verification tags**

- **[V]** — read in a primary source this session (official doc body, source tree, syscap list, API reference).
- **[T]** — vendor/third-party claim read in a primary source; self-reported, not independently reproduced.
- **[?]** — could not verify. Unconfirmed.

**Method note.** `developer.huawei.com` doc pages are an Angular SPA and return a ~1.7 KB empty shell to any fetcher. I recovered the backing JSON API and read the real doc bodies:

```
POST https://svc-drcn.developer.huawei.com/community/servlet/consumer/cn/documentPortal/getDocumentById
body: {"objectId":"<doc-id>","catalogName":"harmonyos-guides","language":"cn"}
POST .../getCatalogTree  body: {"catalogName":"harmonyos-guides","language":"cn"}   # 5742 nodes
```

Every `developer.huawei.com` citation below was read through that API, not scraped from a blog. OpenHarmony mirrors used: `raw.githubusercontent.com/openharmony-rs/openharmony-docs/master/en/...` **[V]**.

---

## 0. Headline verdicts

1. **There is a real, documented, third-party NPU path on HarmonyOS — two of them.** NNRt via MindSpore Lite (high level) and **CANN Kit** (low level, direct Da Vinci NPU, AscendC custom operators, LLM Engine). CANN Kit is *not* system-app-only **[V]**.
2. **GPU compute is NOT impossible.** Vulkan **is** a phone syscap and ships `vkCmdDispatch` / `vkCreateComputePipelines` **[V]**. XEngine Kit is explicitly available to third-party apps **[V]**. The LPR survey's implied "GPU is closed" assumption is wrong.
3. **You cannot measure NPU utilization.** Not from an app, not from `hdc`. This is the single hardest ceiling and it is a *measurement* ceiling, not a compute ceiling. GPU utilization **is** measurable (DevEco Profiler, SP_daemon).
4. **The real ceiling is thermal + background execution, not raw TOPS.** The system has an 8-level `SystemLoadLevel` that explicitly tells you to shed load, and it will suspend/terminate you **[V]**.
5. **Kirin 8020 is a mid-range part** with no published TOPS figure **[T]**.

---

## (A) What you can actually control

| Lever | API | Reachable by 3rd-party app? | Evidence |
|---|---|---|---|
| CPU multithreading | `TaskPool` / `Worker` (ArkTS), `@ohos.taskpool` | Yes | [TaskPool vs Worker](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/taskpool-vs-worker) **[V]** |
| C++ task graph | **FFRT** (Function Flow Runtime Kit) — concurrent queue + graph dependency | Yes | [FFRT Kit](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ffrt-kit) **[V]** |
| Thread→core pinning | `OH_AI_ContextSetThreadAffinityMode` (big/medium cores), `threadAffinityCoreList` | Yes | [mindspore-lite-guidelines](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/mindspore-lite-guidelines) **[V]** |
| Scheduler hinting | **perfHint** / Fast Kit `@hms.fast.schedulingOptimization` — tells the system to raise clocks for a scene | Yes | [perfHint (ArkTS)](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/fast-scheduling-optimization_arkts) / [(C/C++)](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/fast-scheduling-optimization_c) **[V]** |
| NPU inference (high level) | MindSpore Lite + NNRt | Yes | [NNRt 对接开发指导](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/neural-network-runtime-guidelines) **[V]** |
| NPU inference (low level) | **CANN Kit** — `.om` offline model, `OH_NNCompilation_*`, AIPP, AscendC, LLM Engine | Yes, Kirin NPU devices only | [CANN Kit 简介](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-introduction) **[V]** |
| NPU/CPU heterogeneous split | `HMS_HiAIOptions_SetTuningMode(compilation, HIAI_TUNING_MODE_HETER)` | Yes | [CANN 异构](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-optimization) **[V]** |
| Zero-copy in/out | `OH_NNTensor_CreateWithFd` — wrap ION memory as tensors | Yes | [内存零拷贝](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-zero-memory-copy) **[V]** |
| GPU compute | Vulkan compute + XEngine Kit extensions | Yes | [Vulkan Capabilities](https://developer.huawei.com/consumer/en/doc/harmonyos-references/capi-vulkan) **[V]**, [XEngine Kit 简介](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/xengine-kit-introduction) **[V]** |
| Thermal/load awareness | `@ohos.resourceschedule.systemload` (`getLevel`, `on('systemLoadChange')`), `@ohos.thermal` | Yes | [systemload API](https://developer.huawei.com/consumer/cn/doc/harmonyos-references/js-apis-resourceschedule-systemload) **[V]** |

**Cannot control:** GPU/NPU clocks, DVFS governor, NPU scheduler, other apps' priority, whether the NPU driver fuses your graph.

---

## (B) The NPU path, step by step

### Path 1 — MindSpore Lite + NNRt (recommended default; highest-level, least control)

NNRt is a cross-vendor bridge; the vendor NPU driver sits behind an HDI. MindSpore Lite talks to NNRt **without** image composition because both use MindIR **[V]** ([NNRt Kit 简介](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/neural-network-runtime-kit-introduction)).

1. **Convert the model to `.ms`** with `converter_lite`:
   ```
   converter_lite --fmk=ONNX --modelFile=yolo.onnx --outputFile=yolo
   ```
   Docs: [使用MindSpore Lite进行模型转换](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/mindspore-lite-converter-guidelines) **[V]**.
   **Trap:** if the NPU backend is used and clip operators are fused, you get `BuildKirinNPUModel# Create full model kernel failed.` Fix = build the converter **from source** and disable fusion via `converter.cfg`:
   ```ini
   [registry]
   disable_fusion=off
   fusion_blacklists=ConvActivationFusion,MatMulActivationFusion,clip_convert_activation_pass
   ```
   Source: [同 doc, "Disabling the Fusion of Specified Operators"](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/mindspore-lite-converter-guidelines) **[V]**.

2. **Set the device to NNRt.** Native (C/C++), from [mindspore-lite-guidelines](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/mindspore-lite-guidelines) **[V]**:
   ```c
   OH_AI_DeviceInfoHandle nnrt =
       OH_AI_CreateNNRTDeviceInfoByType(OH_AI_NNRTDEVICE_ACCELERATOR);
   OH_AI_DeviceInfoSetPerformanceMode(nnrt, OH_AI_PERFORMANCE_HIGH);
   OH_AI_ContextAddDeviceInfo(context, nnrt);
   // then add CPU too -> heterogeneous: unsupported ops fall back to CPU
   OH_AI_ContextAddDeviceInfo(context, OH_AI_DeviceInfoCreate(OH_AI_DEVICETYPE_CPU));
   ```
   Or enumerate first with `OH_AI_GetAllNNRTDeviceDescs()` and pick by name/type.

   ArkTS equivalent, from [js-apis-mindSporeLite](https://developer.huawei.com/consumer/cn/doc/harmonyos-references/js-apis-mindsporelite) **[V]**:
   ```ts
   let context: mindSporeLite.Context = {};
   context.target = ['cpu', 'nnrt'];
   context.nnrt = {
     deviceID: allDevices[0].deviceID(),
     performanceMode: mindSporeLite.PerformanceMode.PERFORMANCE_EXTREME,
     priority: mindSporeLite.Priority.PRIORITY_HIGH,
   };
   ```
   `PerformanceMode` = `NONE|LOW|MEDIUM|HIGH|EXTREME`; `Priority` = `NONE|LOW|MEDIUM|HIGH` **[V]**.

3. **Quantize.** MindSpore Lite post-training quantization supports weight / full / dynamic quant **[V]** ([训练后量化](https://www.mindspore.cn/lite/docs/zh-CN/master/advanced/quantization.html)):
   - **Weight quant** — best size, "一般" speedup.
   - **Full quant** (INT8 weights+activations, needs 100–500 calibration images, NHWC) — "优" speedup.
   - **Dynamic quant** (weights offline, activations at runtime) — for NLP/Transformer; **"在支持SDOT指令的ARM架构会有进一步的加速效果"** — relevant for Kirin.

   **Reported numbers [T]:** dynamic quant on tinybert: **latency 4.517 ms vs 9.916 ms FP32 (−54.45%)**, model 5.2 MB vs 20 MB. Full-quant accuracy on MobileNetV2: 71.56% → 71.16%. **These are x86 CPU measurements, not NPU measurements** — the doc says so explicitly **[V]**. There is **no official "NPU vs CPU speedup" number anywhere I could find [V]**.

4. **First-run build cost.** NNRt online composition "model loading is slow at first use"; offline models are fast **[V]**. Use the NNRt **model cache** to persist the built model.

**NNRt hard limits [V]:** "NNRt strongly depends on hardware and applies only to devices that support NPUs." Supports **only 56 operators**; **synchronous inference only** (async "in later versions"); no multi-thread concurrent composition; **no emulator support**. CPU and GPU are explicitly *not* NNRt devices — "NNRt provides only the AI inference capability of the underlying AI acceleration hardware, but not common hardware such as the CPU."

### Path 2 — CANN Kit (direct Da Vinci NPU; the real "squeeze" path)

CANN = "Compute Architecture for Neural Networks", the same stack as cloud Ascend, ported to Kirin **[V]**. Constraint: **"仅适用于带有 Kirin NPU 的 Phone、Tablet、PC/2in1、TV 设备"** — no emulator **[V]**.

1. **Get the DDK toolchain** (Ubuntu 64-bit). `DDK-tools-next-6.1.1.0` contains `tools_dopt` (lightweighting), `tools_omg` (model conversion), `tools_ascendc`, `platform` **[V]** ([开发准备](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-preparations)).
   Platform plugins available: **`kirin9020`**, **`kirinx90`**, **`kirin9030`** **[V]**.
2. **Convert to `.om`** with OMG. Optional **AIPP** (hardware image pre-processing: crop/channel-swap/color-space/resize/rotate/pad) — "由于AIPP硬件专用，可以获得较好的推理性能收益" **[V]**.
3. **Quantize.** `Quant_INT8-8` on ResNet-18 shrinks the `.om` from **22.457 MB → 11.9 MB with no accuracy loss** (70.0% → 70.0%) **[T]** ([模型收益](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-model-benefits)). Network-structure-search: ResNet-18 11.69 M params @70.32% → NASEA 10.93 M @72.13% **[T]**.
4. **Check compatibility before shipping:** `HMS_HiAICompatibility_CheckFromFile` / `CheckFromBuffer` → `HIAI_COMPATIBILITY_COMPATIBLE` **[V]** ([FAQ](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-faqs-1)).
5. **Infer.** Find the device named **`"HIAI_F"`** and bind it **[V]** ([模型推理](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-model-inference)):
   ```c
   OH_NNCompilation *c = OH_NNCompilation_ConstructWithOfflineModelBuffer(buf, size);
   OH_NNDevice_GetAllDevicesID(...);            // look for name == "HIAI_F"
   OH_NNCompilation_SetDevice(c, hiaiDeviceId);
   OH_NNCompilation_Build(c);
   OH_NNExecutor *e = OH_NNExecutor_Construct(c);
   OH_NNExecutor_RunSync(e, in, n, out, m);
   ```
6. **Optimize further:**
   - **异构** — `HMS_HiAIOptions_SetTuningMode(c, HIAI_TUNING_MODE_HETER)` + `HMS_HiAIOptions_SetTuningCacheDir(c, "/data/storage/el2/base/files")`. Splits the graph: OP1/OP2/OP5..OPn → CPU, OP3/OP4 → NPU **[V]**.
   - **深度融合** — `HMS_HiAIOptions_SetTuningStrategy(..., "HIAI_TUNING_STRATEGY_ON_DEVICE_TUNING")`, cuts DDR traffic; **only for pre-compile variable-shape** **[V]**.
   - **Zero copy** — `OH_NNTensor_CreateWithFd` to wrap ION memory (e.g. a camera/GPU texture) as tensors, skipping both copies **[V]**.
7. **Custom operators** via **AscendC** (C/C++). Kirin uses a **耦合架构** (Cube+Vector in one core) on Kirin9020/9030/X90, vs the 分离架构 (separate AIC/AIV) of Ascend910B/C **[V]** ([基本架构](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-basic-architecture), [兼容性说明](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-compatibility-rule)).
   **Migration trap [V]:** "若开发者希望在新平台运行其它平台开发的 Ascend C 程序，需要在新平台重新编译并运行" — ISASI/CUBE APIs like `LoadData`/`Mmad` are **not** cross-arch compatible; hardcoded chip specs (`MAX_UB_SIZE = 256*1024`) and `TilingKey` programming are called out as bad practice.
8. **LLM on NPU** — **CANN LM Engine / LLM Engine**: multi-step fusion, memory reuse, zero-copy, LoRA, multimodal, **KV-cache optimization, speculative decoding, cloud-device co-compute** **[V]** ([简介](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-llm-summary)).
   **Supported models (explicit list) [V]:** Qwen2.5-1.5B, DeepSeek-R1-Distill-Qwen-1.5B, Glm-1.5b, Qwen2.5-7B-Instruct, Qwen3-8B. **Hardware: "kirin X90平台"** — i.e. **flagship only**. Kirin 8020 is not on that list **[V]**.
9. **Debug/perf tools** — Netron 5.1.6+ opens `.om` (shows subgraphs and **per-operator device assignment**) **[V]**; `ascendebug kernel --backend simulator` gives per-kernel `total tick` cycle counts on the CAModel simulator — **but "Kirin9020/Kirin9030/KirinX90暂不支持使用该方法进行调优"** for trace-based tuning **[V]** ([Simulator性能仿真](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-simulator-performance-simulation)).
10. **Version check:** `hdc shell param get const.hiai.vendor.hiaiversion` **[V]**.

### Real repos (code-bearing)

| Repo | URL | Backend | Verdict |
|---|---|---|---|
| MNN Local AI Chat | https://github.com/SKL-666666/mnn-local-ai-chat | **MNN + llama.cpp, CPU only** | **Best documented real HarmonyOS LLM app.** API 23. Claims **4 → 40 tok/s (10×)** from rebuilding llama.cpp with `-DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod`; KV-prefix reuse; `n_batch 4096 / n_ubatch 2048`; 3 power modes; thermal guard at 43/45 °C **[T]**. **No NPU** — it's an ARM CPU win. |
| YOLO-HarmonyOS-Vision | https://github.com/Aiyc-02/YOLO-HarmonyOS-Vision | MindSpore Lite, `--targetDevice=CPU` | Pure ArkTS `@kit.MindSporeLiteKit`, real-device only ("暂不支持通过电脑本地模拟器"). Author states the phone **must be on HarmonyOS 6**. Explicitly says **continuous video-stream inference was never stress-tested** — "尚未进行压力验证" **[V]**. |
| llama.cpp-server-ohos | https://github.com/Aloereed/llama.cpp-server-ohos | llama.cpp, OpenMP | 14★, MIT. README claims "硬件加速" but names **only OpenMP and multicore**. **No NPU, no GPU, no benchmark numbers.** Aspirational. **[V]** |
| sherpa-onnx | https://github.com/k2-fsa/sherpa-onnx | ONNX Runtime | Lists HarmonyOS as supported; NPUs supported = **RKNN, QNN, Ascend, Axera, OpenVINO** — **no Kirin/Da Vinci, no NNRt** **[V]**. |
| onnxruntime-ohos-build | https://github.com/JNYZ1/onnxruntime-ohos-build | ORT | 58-byte README. Stub. **[V]** |
| ai_neural_network_runtime | https://gitcode.com/openharmony/ai_neural_network_runtime | NNRt | 3★, Apache-2.0. **This is the NNRt runtime itself.** NNRt opens a north-bound native API and a **south-bound HDI** for chip vendors. Note: **the open-source tree ships no Kirin NPU HDI driver** — that lives in Huawei's closed `libhiai` stack. **[V]** |

**Blunt:** the OSS ecosystem is CPU-bound. Every working HarmonyOS LLM/CV deployment I could read runs on **ARM CPU**. The NPU is reachable **only** through Huawei's own first-party Kits (MindSpore Lite/NNRt, CANN Kit).

---

## (C) GPU verdict — compute is possible

**Vulkan is available to third-party apps.** Evidence chain:

1. `SystemCapability.Graphic.Vulkan` appears in the **phone** syscap list **[V]** ([phone-syscap-list](https://raw.githubusercontent.com/openharmony-rs/openharmony-docs/master/en/application-dev/reference/phone-syscap-list.md)).
2. The SDK supports **Vulkan v1.4.309** with **269 exported functions**, including `vkCmdDispatch`, `vkCmdDispatchBase`, `vkCmdDispatchIndirect`, `vkCreateComputePipelines` **[V]** ([Vulkan Capabilities](https://developer.huawei.com/consumer/en/doc/harmonyos-references/capi-vulkan)).
3. The app-facing guide shows creating a `VkInstance` at `VK_API_VERSION_1_3`, linking `libvulkan.so`, with OHOS-specific extensions `VK_OHOS_surface` / `VK_OHOS_external_memory` **[V]** ([Vulkan Surface Development](https://developer.huawei.com/consumer/en/doc/harmonyos-guides/vulkan-guidelines)). `VK_OHOS_external_memory` gives **zero-copy camera→Vulkan and decoder→Vulkan import** — exactly what a video pipeline wants.
4. There is a shipped sample: [XComponent Component Connecting to Vulkan](https://gitcode.com/openharmony/applications_app_samples/tree/master/code/BasicFeature/Native/NdkVulkan) **[V]**.

**XEngine Kit** (Maleoon GPU) is explicitly third-party, and includes compute-flavoured features **[V]** ([XEngine Kit 简介](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/xengine-kit-introduction)):

- **高性能GPU排序** (HPS radix sort) — `HMS_XEG_CreateHPS` / `HMS_XEG_CmdRadixSortHPS` on Vulkan. "依托于华为Maleoon GPU的软硬结合优化，效率更高" **[V]** ([高性能GPU排序](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/xengine-kit-high-performance-gpu-sorting)).
- **Subpass Shading** — `VK_HUAWEI_subpass_shading`, lets a **Compute Shader** run in a subpass and read the tile buffer via `SubpassLoad` **[V]**.
- Spatio/temporal AI upscaling — **GPU/NPU collaborative**.
- Constraints: **Maleoon GPU only**, **China mainland only** (excl. HK/Macau/Taiwan), no emulator; features gated by `HMS_XEG_EnumerateDeviceExtensionProperties` **[V]**.

**What is NOT available:**

- **OpenCL** — no app-facing OpenCL Kit, no OpenCL syscap, no OpenCL doc in the 5742-node catalog. `hirofiler` has `RES_GPU_CL_BUFFER`/`RES_GPU_CL_IMAGE` memory-accounting tags, which only proves a driver *exists*, not that it's exposed **[V]**. **Treat OpenCL as unavailable.**
- **WebGPU** — no WebGPU doc anywhere in the catalog. Only **WebGL** exists, and its own doc says it is "基于OpenGL裁剪的OpenGL ES" and **"目前该功能仅支持使用兼容JS的类Web开发范式开发"** **[V]** ([使用WebGL绘制图形](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/webgl-2d-guidelines)). No compute shaders.

**Verdict:** GPU compute via **Vulkan compute + XEngine HPS** is real and shippable. Do not count on OpenCL or WebGPU.

---

## (D) How to measure — and what you can't

| Tool | CPU | GPU | NPU | Third-party reachable? |
|---|---|---|---|---|
| **DevEco Profiler — Realtime Monitor** | ✅ per-process | ✅ **GPU utilization %** | ❌ | Yes (USB or wireless, real device only) |
| **DevEco Profiler — GPU template** | ✅ | ✅ **per-hardware-module counters** | ❌ | Yes. DevEco Studio **6.0.0 Beta3+**, Phone only, sampling 1–1000 ms |
| **SP_daemon** (SmartPerf Device CLI) | ✅ freq+load | ✅ `-g` freq+load | ❌ **only `npu_thermal` (temperature)** | Pre-installed since API 9; run over `hdc shell` |
| **hidumper** | ✅ `--cpuusage`, `--cpufreq` | ❌ | ❌ | Yes, but no GPU/NPU counters exist |
| **hiperf** | ✅ `hw-cpu-cycles`, `hw-instructions`, call stacks | ❌ | ❌ | Yes, non-root |
| **SmartPerf-Host** | ✅ swimlanes | ✅ frame-level | ❌ | Yes (PC tool + device) |

Sources: [实时监控](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/realtime-monitor) **[V]**, [GPU活动分析](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ide-profiler-gpu) **[V]**, [HiSmartPerf Device性能使用指导](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/smartperf-guidelines) **[V]**, [hidumper](https://raw.githubusercontent.com/openharmony-rs/openharmony-docs/master/en/application-dev/dfx/hidumper.md) **[V]**, [hiperf](https://raw.githubusercontent.com/openharmony-rs/openharmony-docs/master/en/application-dev/dfx/hiperf.md) **[V]**.

**Is there an Android `dumpsys` / Snapdragon Profiler equivalent?** Partially. `hidumper -s <SA> -a "<option>"` is the `dumpsys` analogue (`hidumper -ls` lists SAs). `hiperf` is the `perf` analogue. `SP_daemon` is the closest to Snapdragon Profiler. **But there is no NPU utilization counter in any of them.**

`SP_daemon` output, real sample **[V]**:
```
order:123 gpuFrequency=279000000
order:124 gpuLoad=0.000000
order:127 gpu=47.000000          <- temperature
order:128 npu_thermal=35.000000  <- temperature ONLY, not utilization
```
Note `-fds` is documented as **"available only for the root user"** — the rest is shell-accessible **[V]**.

**What hdc/hdc shell can expose:** `hidumper` (mem/cpuusage/cpufreq/faultlog/window trees/IPC), `hiperf`, `hitrace`, `SP_daemon`, `hiprofiler_cmd`, `param get`. **Not** available: kernel symbols/root-mode sampling, and — critically — **no NPU or GPU hardware counters**. `hiprofiler`'s GPU plugin reports **per-process GPU usage**; its NPU story is absent **[V]** ([hiprofiler](https://raw.githubusercontent.com/openharmony-rs/openharmony-docs/master/en/application-dev/dfx/hiprofiler.md)).

**Can you prove you "squeezed" the NPU? — Blunt answer: no, not directly.**
- You **cannot** read NPU utilization, NPU clock, or NPU power from an app or from `hdc`.
- `npu_thermal` is a **temperature**, not a load. A hot NPU is consistent with both "saturated" and "idle but next to a hot SoC".
- The only NPU numbers Huawei publishes are **`.om` model-size and accuracy deltas**, never throughput **[V]**.
- `SystemCapability.Graphics.XEngine` gives you **GPU** capability queries, not NPU.

**What you CAN prove:** end-to-end **wall-clock latency** and **throughput (FPS / tok/s)** of your own pipeline, plus **which device each operator was assigned to** (Netron on the `.om`, or `hiprofiler` GPU lane). The honest claim is *"latency dropped from X to Y and the graph shows N ops on HIAI_F"* — **not** *"NPU is at 90% utilization."* The only way to approach a utilization claim is to A/B: same model, `targetDevice=CPU` vs `nnrt`/`HIAI_F`, same input, compare latency. **That delta is your evidence. Build the harness for it from day one.**

---

## (E) Top 5 gotchas that kill naive "squeeze everything" plans

**1. Thermal is a first-class, app-visible kill switch.**
`SystemLoadLevel` has **8 levels** and the doc tells you what to do at each **[V]** ([systemload](https://developer.huawei.com/consumer/cn/doc/harmonyos-references/js-apis-resourceschedule-systemload)):

| Level | Value | Official instruction |
|---|---|---|
| LOW | 0 | — |
| NORMAL | 1 | "downgrade or reduce the load of imperceptible services" |
| MEDIUM | 2 | "stop or delay some imperceptible services" |
| HIGH | 3 | "**stop all imperceptible services**" |
| OVERHEATED | 4 | "stop all imperceptible services and **downgrade major foreground services**" |
| WARNING | 5 | "**stop all imperceptible services and downgrade major foreground services to the maximum extent**" |
| EMERGENCY | 6 | "**stop all services except those for fundamental use**" |
| ESCAPE | 7 | "stop all services" |

A continuous-video inference loop *is* the "imperceptible service" this API is designed to kill. Subscribe to `systemLoad.on('systemLoadChange')` and `thermal.registerThermalLevelCallback` and degrade **before** you get killed. The MNN app's real-world numbers — **≥45 °C stop generating, ≥43 °C auto-switch to power-save, <40 °C restore** — are the pattern to copy **[T]**.

**2. Background execution will end your long run — and "computing" is not an allowed continuous-task type.**
- Backgrounded apps are **suspended after a short period** **[V]** ([reasonable-running-backgroundTask](https://raw.githubusercontent.com/openharmony-rs/openharmony-docs/master/en/application-dev/performance/reasonable-running-backgroundTask.md)).
- **Transient task** buys you only ~1 minute; the doc's own profile window is "less than one minute" **[V]**.
- **Continuous task** types are enumerated, and there is **no general "AI inference" type**. `TASK_KEEPING` ("Computing tasks") is the only one that fits — and it is **restricted**: *"Starting from API version 21, this capability is available for 2-in-1 devices, and non-2-in-1 devices that have obtained the ACL permission `ohos.permission.KEEP_BACKGROUND_RUNNING_SYSTEM`. In API version 20 and earlier, this task type is limited to PCs/2-in-1 devices only."* **[V]**
- Even with a valid continuous task: *"If the background load of the process that runs a continuous task is **higher than the corresponding typical load for a long period of time**, the system performs certain control. The application will be **suspended or terminated**."* **[V]**
- The system **actively verifies** you are doing the declared work, and the user deleting the notification terminates the task **[V]**.

**Conclusion: continuous video inference in the background is not sustainable. It is barely sustainable in the foreground.**

**3. Operator coverage, not FLOPs, is what breaks your model.**
NNRt supports **56 operators** **[V]**. CANN Kit has its own support list, and the FAQ "算法在设计模型时，如何确认哪些算子在CANN上性能较优？" exists precisely because it varies **[V]**. Every unsupported op falls back to CPU and, in a heterogeneous context, forces a **sync + data round-trip**, which can cost more than the NPU saved. The YOLO-HarmonyOS repo explicitly lists **tensor-output-shape incompatibility** (`[1,6,300]` vs `[1,300,6]`) as an open problem **[V]**. **Profile op coverage before you write app code.**

**4. The first-run cost is real and the cache is easy to forget.**
NNRt online composition is "slow at first use" **[V]**. Without `OH_NNCompilation_SetTuningCacheDir` / the NNRt model cache, every cold start eats the build. On CANN, `.om` build is fast but you must ship a **per-Kirin-platform** `.om` (plugins are `kirin9020` / `kirinx90` / `kirin9030`) **[V]** — a single `.om` is not portable, and `HMS_HiAICompatibility_Check*` exists because of it.

**5. Kirin 8020 is mid-range, and the flagship-only features won't be there.**
- cpudb classifies it **"Mid range"**, 7 nm SMIC, 1×2.285 + 3×2.05 + 4×1.3 GHz, Maleoon 920 @840 MHz, Da Vinci NPU **[T]** ([cpudb](https://www.cpudb.cc/compare/samsung-exynos-1580-vs-hisilicon-kirin-8020)).
- **No TOPS figure is published.** cpudb leaves it blank; the 14.7 TOPS in that table belongs to the **Exynos 1580** column, not Kirin. **Anyone quoting a Kirin 8020 TOPS number is guessing. Treat all such numbers as rumor.**
- Huawei's launch claims are **relative deltas only**: NPU **+128%**, CPU multi-core +52%, GPU +26% vs the previous gen, and +62% overall on HarmonyOS 6 **[T]** ([ZOL](https://ai.zol.com.cn/1104/11046813.html)). Percentages without a baseline are not a TOPS figure.
- **CANN LM Engine's supported hardware is "kirin X90平台"** — the LLM path is flagship-gated **[V]**. Do not assume the 8020 gets it.

---

## Rumor / unverified ledger

| Claim | Status |
|---|---|
| Kirin 8020 NPU TOPS | **[?] No official figure exists.** cpudb blank. The "+128%" is a relative delta **[T]**. Any absolute TOPS is rumor. |
| Kirin 8020 is flagship | **False.** cpudb: "Mid range" **[T]**. It was a *Pro/Ultra* chip, now demoted to nova 15 standard **[T]**. |
| "MindSpore Lite gives N× NPU speedup" | **[?] No official NPU-vs-CPU speedup number found.** All published quant numbers are **x86 CPU** **[V]**. |
| NPU utilization is readable | **False.** No API, no hdc command. Only `npu_thermal` (temperature) **[V]**. |
| OpenCL on HarmonyOS | **[?] No app-facing evidence.** Driver memory tags exist in hiprofiler only **[V]**. Assume unavailable. |
| WebGPU on HarmonyOS | **False.** No docs; only WebGL (GLES-derived, JS-classic paradigm only) **[V]**. |
| Third-party apps can't use the NPU | **False.** CANN Kit + NNRt are both documented for third-party apps **[V]**. |
| llama.cpp on HarmonyOS uses the NPU | **False.** Every repo read uses CPU/OpenMP/dotprod **[V]**. |
| Continuous background video inference is viable | **False.** No suitable continuous-task type for non-2-in-1 without ACL; sustained-load suspension is documented **[V]**. |

---

## Sources

Official docs (read via the `documentPortal` JSON API unless noted):
[CANN Kit 简介](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-introduction) ·
[CANN 异构](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-optimization) ·
[CANN 模型推理](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-model-inference) ·
[CANN 内存零拷贝](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-zero-memory-copy) ·
[CANN 深度融合](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-in-depth-convergence) ·
[CANN 开发准备](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-preparations) ·
[CANN 模型收益](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-model-benefits) ·
[CANN 兼容性说明](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-compatibility-rule) ·
[CANN 基本架构](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-basic-architecture) ·
[CANN LLM 简介](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-llm-summary) ·
[CANN Simulator 仿真](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/cannkit-simulator-performance-simulation) ·
[NNRt 对接开发指导](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/neural-network-runtime-guidelines) ·
[NNRt Kit 简介](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/neural-network-runtime-kit-introduction) ·
[MindSpore Lite 模型推理 (C/C++)](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/mindspore-lite-guidelines) ·
[MindSpore Lite 模型转换](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/mindspore-lite-converter-guidelines) ·
[js-apis-mindSporeLite](https://developer.huawei.com/consumer/cn/doc/harmonyos-references/js-apis-mindsporelite) ·
[XEngine Kit 简介](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/xengine-kit-introduction) ·
[高性能GPU排序](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/xengine-kit-high-performance-gpu-sorting) ·
[Subpass Shading](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/xengine-kit-subpass-shading) ·
[XEngine 开发准备](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/xengine-kit-preparations) ·
[Vulkan Capabilities](https://developer.huawei.com/consumer/en/doc/harmonyos-references/capi-vulkan) ·
[Vulkan Surface Development](https://developer.huawei.com/consumer/en/doc/harmonyos-guides/vulkan-guidelines) ·
[WebGL 绘制图形](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/webgl-2d-guidelines) ·
[实时监控](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/realtime-monitor) ·
[GPU活动分析](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ide-profiler-gpu) ·
[DevEco Profiler 简介](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ide-profiler) ·
[systemload API](https://developer.huawei.com/consumer/cn/doc/harmonyos-references/js-apis-resourceschedule-systemload) ·
[thermal API](https://developer.huawei.com/consumer/cn/doc/harmonyos-references/js-apis-thermal) ·
[长时任务(ArkTS)](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/continuous-task) ·
[长时任务开发指导 (TaskPool)](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/long-time-task-guide) ·
[常驻任务开发指导 (Worker)](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/resident-task-guide) ·
[后台任务使用](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/standard-background-task) ·
[TaskPool和Worker对比](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/taskpool-vs-worker) ·
[FFRT Kit](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ffrt-kit) ·
[perfHint (C/C++)](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/fast-scheduling-optimization_c) ·
[SmartPerf Device User Guide](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/smartperf-guidelines)

OpenHarmony doc mirror (`raw.githubusercontent.com/openharmony-rs/openharmony-docs/master/`):
[hidumper](https://raw.githubusercontent.com/openharmony-rs/openharmony-docs/master/en/application-dev/dfx/hidumper.md) ·
[hiperf](https://raw.githubusercontent.com/openharmony-rs/openharmony-docs/master/en/application-dev/dfx/hiperf.md) ·
[hiprofiler](https://raw.githubusercontent.com/openharmony-rs/openharmony-docs/master/en/application-dev/dfx/hiprofiler.md) ·
[phone syscap list](https://raw.githubusercontent.com/openharmony-rs/openharmony-docs/master/en/application-dev/reference/phone-syscap-list.md) ·
[NNRt intro](https://raw.githubusercontent.com/openharmony-rs/openharmony-docs/master/en/application-dev/ai/nnrt/Neural-Network-Runtime-Kit-Introduction.md) ·
[Vulkan overview](https://raw.githubusercontent.com/openharmony-rs/openharmony-docs/master/en/application-dev/reference/native-lib/vulkan-overview.md) ·
[continuous-task](https://raw.githubusercontent.com/openharmony-rs/openharmony-docs/master/en/application-dev/task-management/continuous-task.md) ·
[reasonable-running-backgroundTask](https://raw.githubusercontent.com/openharmony-rs/openharmony-docs/master/en/application-dev/performance/reasonable-running-backgroundTask.md)

MindSpore: [训练后量化](https://www.mindspore.cn/lite/docs/zh-CN/master/advanced/quantization.html) · [下载 MindSpore Lite](https://www.mindspore.cn/lite/docs/zh-CN/master/use/downloads.html) (confirms "支持业界通用的 CPU、**Kirin NPU** 硬件设备")

Repos: [mnn-local-ai-chat](https://github.com/SKL-666666/mnn-local-ai-chat) · [YOLO-HarmonyOS-Vision](https://github.com/Aiyc-02/YOLO-HarmonyOS-Vision) · [llama.cpp-server-ohos](https://github.com/Aloereed/llama.cpp-server-ohos) · [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) · [onnxruntime-ohos-build](https://github.com/JNYZ1/onnxruntime-ohos-build) · [ai_neural_network_runtime](https://gitcode.com/openharmony/ai_neural_network_runtime) · [NdkVulkan sample](https://gitcode.com/openharmony/applications_app_samples/tree/master/code/BasicFeature/Native/NdkVulkan)

Hardware: [cpudb Kirin 8020](https://www.cpudb.cc/compare/samsung-exynos-1580-vs-hisilicon-kirin-8020) · [ZOL nova 15 发布](https://ai.zol.com.cn/1104/11046813.html)
