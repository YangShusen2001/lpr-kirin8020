# 60 fps 到底能不能拿到：API 面、框架源码与 NDK 三路对照

**日期**：2026-09-22
**设备**：HUAWEI nova 14 Pro（MIA-AL00）· 麒麟 8020 · HarmonyOS 6.1.0.135 · API 24
**SDK**：`D:\IDE\DevEco_Studio\sdk\default\`（`sdk-pkg.json`：apiVersion 24 / HarmonyOS 6.1.1 / 6.1.1.125 Release）
**触发**：设备报 `getSupportedFrameRates()` = `[1-30, 60-60]`，`setFrameRate(60,60)` 被接受、
`getActiveFrameRate()` 回报 `60-60`，但实测到达率恒为 ~29.8–30 fps。

**一句话结论**：**框架没有骗人，也没有隐藏开关。`60-60` 是厂商 HAL 通过元数据
声明的一条"能力"，框架原样透传；但框架层**从不校验、也从不保证**这条能力会被兑现。
把 `mCurMaxFps` 从 20 抬到 30 的那个 `setMaxFps()` 不在 OpenHarmony 代码里
（全仓 grep 命中 0 次），它在厂商闭源 daemon 里 —— **这就是钳位点**。

---

## 一、结论表

| # | 问题 | 结论 | 证据强度 |
|---|---|---|---|
| 1 | `FrameRateRange` / `getSupportedFrameRates()` / `setFrameRate()` 是什么 | 三者都是**输出（Output）级**接口，返回的是**绑定的那个 Profile 的 `fps_`**，而 `fps_` 由 HAL 元数据填充 → **是 HAL 能力声明，不是框架计算值** | **确证**（源码级） |
| 1b | `60-60`（min==max）是否有特殊含义 | 有：表示**固定帧率**（fixed fps），与 `min<max` 的"范围帧率"是两种不同语义，框架和文档都分别处理 | **确证**（源码+文档） |
| 1c | 是否存在 "highFPS / 高帧率 session mode" | C++ 内部有 `SceneMode::HIGH_FRAME_RATE = 13`，但**未暴露给任何 ArkTS/NDK 应用**；ArkTS `SceneMode` 只有 3 个成员 | **确证**（源码级） |
| 2 | 框架是否**官方支持** 60/120 fps | 框架**内部**支持 120/240（慢动作路径），但**对三方应用全部屏蔽**（非系统应用被显式 `continue` 跳过）；`getSupportedFrameRatesForVideo` **不存在** | **确证**（源码级） |
| 3 | NDK / C API 是否比 ArkTS 多给帧率能力 | **完全不多**。帧率面逐函数一一对应；NDK 多出来的是 SceneMode/ProfileLevel 相关接口，与帧率无关 | **确证**（本地头文件逐条比对） |
| 4 | ArkTS 面是否有我们没用到的帧率相关接口 | **没有**。全部 `FrameRate*` 出现点已穷举（见第四节）；`CameraMode` 枚举**根本不存在**；`HighResolutionPhotoSession` 在公开 `.d.ts` 里**不存在** | **确证**（本地 `.d.ts` 全文检索） |
| 5 | 换 VideoSession 能否解锁 60 fps | PhotoSession 与 VideoSession **都**允许 `setFrameRate`，且**都不做实质校验**；差别只在于查哪一套 Profile 集合。**推断换 VideoSession 也拿不到 60** | **推断**（源码级，缺真机验证） |
| 6 | `60-60` 是否是 profile 专属的 | **是**。`getSupportedFrameRates()` 先按 **format + 宽高精确匹配**过滤本 output 绑定的 Profile，再取这些 Profile 的 `fps_` 去重 → **逐 output、逐 profile 不同** | **确证**（源码级） |
| ★ | 为什么实测只有 30 | 厂商闭源 daemon 动态钳位（`CameraDaemon/IPS_STREAMIMG: Misc.cpp:4026 setMaxFps`）。该符号**不在 OpenHarmony 仓库中** | **推断**（框架侧排除 + 日志侧证） |

---

## 二、逐题作答

### 第 1 题：`FrameRateRange` / `getSupportedFrameRates()` / `setFrameRate()` 的确切语义

#### 1.1 API 面（本地 SDK，权威）

`D:\IDE\DevEco_Studio\sdk\default\openharmony\ets\api\@ohos.multimedia.camera.d.ts`

`FrameRateRange` 定义在 **L289–L341**（`@typedef` 块 L289–L303，`interface` L304–L341），
两个字段都 `readonly`，`@since 10`：

```ts
// L304-341（节选，doc 注释已省略）
interface FrameRateRange {
    readonly min: number;   // L322  "Min frame rate."
    readonly max: number;   // L340  "Max frame rate."
}
```

`PreviewOutput` 上的三个帧率接口（**L7048–L7101**）：

| 接口 | 行号 | `@since` | 文档注释要点 |
|---|---|---|---|
| `getSupportedFrameRates(): Array<FrameRateRange>` | **L7063** | 12 | `"Get supported frame rates which can be set during session running."` |
| `setFrameRate(minFps, maxFps): void` | **L7085** | 12 | `throws 7400101` / `throws 7400110`；`"The supported frame rate range can be queried via the getSupportedFrameRates interface before setting."` |
| `getActiveFrameRate(): FrameRateRange` | **L7101** | 12 | `"Get active frame rate range which has been set before."` / `"Queryable after setting the frame rate for the preview stream using the setFrameRate interface."` |

`VideoOutput` 上是**逐字相同**的三件套：**L8671 / L8693 / L8709**。

> **关键措辞**：官方注释说的是 *"which can be set during session running"*（**会话运行期间可设置**），
> 不是 *"the frame rates the device can deliver"*。这是本次全部困惑的源头。

#### 1.2 官方中文文档

`openharmony/docs` → `zh-cn/application-dev/reference/apis-camera-kit/arkts-apis-camera-PreviewOutput.md`

- **L209–L232** `getSupportedFrameRates<sup>12+</sup>`：`"查询支持的帧率范围。"`
  返回值说明（L223）：`"支持的帧率范围列表。若接口调用失败，返回undefined。"`
- **L234–L271** `setFrameRate<sup>12+</sup>`：`"设置预览流帧率范围，设置的范围必须在支持的帧率范围内。"`
  **L242–L243 有一句决定性的话**：

  > **说明：**
  > 仅在 [PhotoSession](arkts-apis-camera-PhotoSession.md) 或 [VideoSession](arkts-apis-camera-VideoSession.md) 模式下支持。

  参数表 L253–L254：`minFps` / `maxFps`，`"当传入的最大值小于最小值时，传参异常，接口不生效。"`
- **L273–L294** `getActiveFrameRate<sup>12+</sup>`：`"获取已设置的帧率范围。"` /
  `"使用 setFrameRate 接口对预览流设置过帧率后可查询。"`

错误码 `7400110` 的官方解释（`errorcode-camera.md` L175–L191）：

> ## 7400110 与当前配置存在冲突
> **错误描述**：由于当前提交的配置与设备所支持的配置存在不兼容。
> **可能原因**：**设置预览流的帧率超出设备所支持的帧率**等。

#### 1.3 框架源码：它到底从哪里取值

`multimedia_camera_framework` · `frameworks/native/camera/base/src/output/preview_output.cpp`

**`GetSupportedFrameRates()` — L487–L520**（核心逻辑，逐字）：

```cpp
// L487
std::vector<std::vector<int32_t>> PreviewOutput::GetSupportedFrameRates()
{
    auto session = GetSession();
    CHECK_RETURN_RET(session == nullptr, {});
    auto inputDevice = session->GetInputDevice();
    CHECK_RETURN_RET(inputDevice == nullptr, {});
    sptr<CameraDevice> camera = inputDevice->GetCameraDeviceInfo();
    SceneMode curMode = session->GetMode();                    // ← 用当前会话的 SceneMode

    sptr<CameraOutputCapability> cameraOutputCapability = CameraManager::GetInstance()->
                                                          GetSupportedOutputCapability(camera, curMode);
    CHECK_RETURN_RET(cameraOutputCapability == nullptr, {});
    std::vector<Profile> supportedProfiles = cameraOutputCapability->GetPreviewProfiles();
    supportedProfiles.erase(std::remove_if(                     // ← L504
        supportedProfiles.begin(), supportedProfiles.end(),
        [&](Profile& profile) {
            return profile.format_ != previewFormat_ ||         // ← L505 格式必须精确相同
                   profile.GetSize().height != previewSize_.height ||
                   profile.GetSize().width  != previewSize_.width;  // 宽高必须精确相同
        }), supportedProfiles.end());
    std::vector<std::vector<int32_t>> supportedFrameRatesRange;
    for (auto item : supportedProfiles) {
        std::vector<int32_t> supportedFrameRatesItem = {item.fps_.minFps, item.fps_.maxFps};  // ← L511
        supportedFrameRatesRange.emplace_back(supportedFrameRatesItem);
    }
    std::set<std::vector<int>> set(supportedFrameRatesRange.begin(), supportedFrameRatesRange.end());
    supportedFrameRatesRange.assign(set.begin(), set.end());     // 去重
    return supportedFrameRatesRange;
}
```

**`canSetFrameRateRange()` — L738–L755**（校验的全部内容）：

```cpp
int32_t PreviewOutput::canSetFrameRateRange(int32_t minFrameRate, int32_t maxFrameRate)
{
    auto session = GetSession();
    CHECK_RETURN_RET_ELOG(session == nullptr, CameraErrorCode::SESSION_NOT_CONFIG,
        "PreviewOutput::canSetFrameRateRange Can not set frame rate range without commit session");
    CHECK_RETURN_RET_ELOG(!session->CanSetFrameRateRange(minFrameRate, maxFrameRate, this),
        CameraErrorCode::UNRESOLVED_CONFLICTS_BETWEEN_STREAMS,          // ← 7400110 来源
        "PreviewOutput::canSetFrameRateRange Can not set frame rate range with wrong state of output");
    int32_t minIndex = 0;
    int32_t maxIndex = 1;
    std::vector<std::vector<int32_t>> supportedFrameRange = GetSupportedFrameRates();
    for (auto item : supportedFrameRange) {
        CHECK_RETURN_RET(item[minIndex] <= minFrameRate && item[maxIndex] >= maxFrameRate,
            CameraErrorCode::SUCCESS);                                   // ← 只要"被包含"就放行
    }
    MEDIA_WARNING_LOG("PreviewOutput::canSetFrameRateRange Can not set frame rate range with invalid parameters");
    return CameraErrorCode::INVALID_ARGUMENT;
}
```

**`SetFrameRate()` — L459–L485**：校验通过后调 `itemStream->SetFrameRate(min,max)` 下发到 HDI 流，
然后**把值记在本地** `SetFrameRateRange()`（L440–L445，写 `previewFrameRateRange_`）。

> #### 结论（确证）
> 1. **返回的是 HAL 声明值**：`item.fps_` 直接来自 `CameraOutputCapability` 的 Profile，
>    而 Profile 由 `CameraManager` 从 HAL 元数据解析而来（见第 6 题）。
>    **框架没有做任何"能不能真出这个帧率"的推断。**
> 2. **校验极弱**：只要请求区间被**任意一条**已声明区间包含，就返回 `SUCCESS`。
>    所以 `60-60` 被接受完全符合设计 —— 声明里有 `60-60`，请求 `60-60`，包含关系成立。
> 3. **框架不兑现、不复查**：`SetFrameRate` 之后框架**再也不看实际帧率**。
>    `getActiveFrameRate()` 读的是本地缓存的"上次设置值"，**不是实测值**。

#### 1.4 `60-60`（min==max）是"固定帧率"，语义确实特殊

`frameworks/native/camera/base/src/session/capture_session.cpp` **L671–L684**：

```cpp
bool CaptureSession::CheckFrameRateRangeWithCurrentFps(int32_t curMinFps, int32_t curMaxFps,
                                                       int32_t minFps, int32_t maxFps)
{
    CHECK_RETURN_RET_ELOG(minFps == 0 || curMinFps == 0, false,
        "CaptureSession::CheckFrameRateRangeWithCurrentFps can not set zero!");
    if (curMinFps == curMaxFps && minFps == maxFps &&
        (minFps % curMinFps == 0 || curMinFps % minFps == 0)) {   // ← 两边都是固定帧率：约数关系即可
        return true;
    } else if (curMinFps != curMaxFps && curMinFps == minFps && curMaxFps == maxFps) {
        return true;                                              // ← 两边都是范围：必须完全相同
    }
    MEDIA_WARNING_LOG("CaptureSession::CheckFrameRateRangeWithCurrentFps check is not pass!");
    return false;
}
```

官方文档把这两种语义称为 **"固定帧率"** 与 **"范围帧率"**，见
`media/camera/camera-recording.md` **L137–L141**：

> - 在设置预览流帧率时，需要先通过 getActiveFrameRate 查询当前录像流的帧率。
> - 当录像流已设置过**范围帧率**时，预览流帧率必须设置与其相同的范围帧率。
> - 当录像流已设置过**固定帧率**时，预览流帧率要设置成录像帧率的**约数**，且必须也为固定帧率。

> **所以 `60-60` 不是一个"怪值"，它是合法且常见的一等公民**：
> 设备在告诉你"这条 profile 存在一个 **锁定 60 fps** 的档位"。
> 它没有被特殊对待成"高帧率模式"，只是一个 min==max 的区间。

---

### 第 2 题：框架是否**官方支持**高帧率（60/120）

#### 2.1 内部：有。120 / 240 走的是"慢动作"路径

`capture_session.cpp` **L59–L61**：

```cpp
constexpr int32_t FRAMERATE_120 = 120;
constexpr int32_t FRAMERATE_240 = 240;
constexpr int32_t CONTROL_CENTER_FPS_MAX = 30;
```

`capture_session.cpp` **L924–L945** —— `AdaptOutputVideoHighFrameRate`，函数名里就有 "HighFrameRate"：

```cpp
int32_t CaptureSession::AdaptOutputVideoHighFrameRate(sptr<CaptureOutput>& output,
    sptr<ICaptureSession>& captureSession)
{
    if (GetMode() == SceneMode::VIDEO && output->GetOutputType() == CAPTURE_OUTPUT_TYPE_VIDEO) {
        std::vector<int32_t> videoFrameRates = output->GetVideoProfile()->GetFrameRates();
        CHECK_RETURN_RET_ELOG(videoFrameRates.empty(), CameraErrorCode::INVALID_ARGUMENT, "videoFrameRates is empty!");
        if (videoFrameRates[0] == FRAMERATE_120 || videoFrameRates[0] == FRAMERATE_240) {
            captureSession->SetFeatureMode(SceneMode::HIGH_FRAME_RATE);   // ← L938
            SetMode(SceneMode::HIGH_FRAME_RATE);                          // ← L939
            return CameraErrorCode::SUCCESS;
        }
    }
    return CameraErrorCode::SUCCESS;
}
```

这个函数在 `CaptureSession::AddOutput()` 里被**每次加输出时调用**（**L895**）：

```cpp
int32_t ret = AdaptOutputVideoHighFrameRate(output, captureSession);
CHECK_RETURN_RET_ELOG(ret != CameraErrorCode::SUCCESS, ServiceToCameraError(CAMERA_INVALID_ARG),
    "CaptureSession::AddOutput An Error in the AdaptOutputVideoHighFrameRate");
```

`frameworks/native/camera/base/src/output/video_output.cpp` **L141–L144 / L175–L181**：
帧率 ≥ 120 时**强制关掉人脸检测**（省算力）：

```cpp
if (!GetFrameRateRange().empty() && GetFrameRateRange()[0] >= FRAMERATE_120) {
    MEDIA_INFO_LOG("EnableFaceDetection is call");
    session->EnableFaceDetection(false);
}
```

#### 2.2 但是：**对三方应用被显式屏蔽**

`frameworks/native/camera/base/src/input/camera_manager.cpp` **L2750–L2760**：

```cpp
void CameraManager::CreateProfile4StreamType(ProfilesWrapper& profilesWrapper, OutputCapStreamType streamType,
    uint32_t modeIndex, uint32_t streamIndex, ExtendInfo extendInfo)
{
    const int frameRate120 = 120;
    const int frameRate240 = 240;
    for (uint32_t k = 0; k < extendInfo.modeInfo[modeIndex].streamInfo[streamIndex].detailInfoCount; k++) {
        const auto& detailInfo = extendInfo.modeInfo[modeIndex].streamInfo[streamIndex].detailInfo[k];
        // Skip profiles with unsupported frame rates for non-system apps
        if ((detailInfo.minFps == frameRate120 || detailInfo.minFps == frameRate240) && !IsSystemApp()) {
            continue;                                        // ← L2759 直接丢弃
        }
```

同样的门在 ProfileLevel 路径上（**L2544–L2556**）：

```cpp
void CameraManager::ParseProfileLevel(ProfilesWrapper& profilesWrapper, const int32_t modeName,
    const camera_metadata_item_t& item)
{
    std::vector<SpecInfo> specInfos;
    ProfileLevelInfo modeInfo = {};
    if (IsSystemApp() && modeName == SceneMode::VIDEO) {                 // ← L2549 仅系统应用
        CameraAbilityParseUtil::GetModeInfo(SceneMode::HIGH_FRAME_RATE, item, modeInfo);
        specInfos.insert(specInfos.end(), modeInfo.specInfos.begin(), modeInfo.specInfos.end());
    }
```

> **注意门槛是 `minFps == 120 || minFps == 240`，不是 `>30`。**
> 所以 **60 fps 不在被屏蔽的集合里** —— 60 是"三方应用可声明"的档位。
> 这与设备报出 `60-60` 完全一致：**`60-60` 是给三方应用看的合法档位**。

#### 2.3 `SceneMode::HIGH_FRAME_RATE` 的确切定义与暴露情况

`interfaces/inner_api/native/camera/include/session/capture_scene_const.h`

**L25–L44**（`JsSceneMode`，即**能过 NAPI 到 JS 的那一套**）：

```cpp
enum JsSceneMode : int32_t {
    JS_NORMAL = 0, JS_CAPTURE = 1, JS_VIDEO = 2, JS_PORTRAIT = 3, JS_NIGHT = 4,
    JS_PROFESSIONAL_PHOTO = 5, JS_PROFESSIONAL_VIDEO = 6, JS_SLOW_MOTION = 7,
    JS_CAPTURE_MARCO = 8, JS_VIDEO_MARCO = 9, JS_LIGHT_PAINTING = 10,
    JS_HIGH_RES_PHOTO = 11, JS_SECURE_CAMERA = 12, JS_QUICK_SHOT_PHOTO = 13,
    JS_APERTURE_VIDEO = 14, JS_PANORAMA_PHOTO = 15, JS_TIMELAPSE_PHOTO = 16,
    JS_FLUORESCENCE_PHOTO = 17,
};   // ← 没有 HIGH_FRAME_RATE
```

**L46–L68**（`SceneMode`，内部枚举 —— 有）：

```cpp
enum SceneMode : int32_t {
    NORMAL = 0, CAPTURE = 1, VIDEO = 2, PORTRAIT = 3, NIGHT = 4, PROFESSIONAL = 5,
    SLOW_MOTION = 6, SCAN = 7, CAPTURE_MACRO = 8, VIDEO_MACRO = 9,
    PROFESSIONAL_PHOTO = 11, PROFESSIONAL_VIDEO = 12,
    HIGH_FRAME_RATE = 13,          // ← L59  ★ 就是它
    HIGH_RES_PHOTO = 14, SECURE = 15, QUICK_SHOT_PHOTO = 16, LIGHT_PAINTING = 17,
    PANORAMA_PHOTO = 18, TIMELAPSE_PHOTO = 19, APERTURE_VIDEO = 20, FLUORESCENCE_PHOTO = 21,
};
```

NAPI 映射表（`frameworks/js/camera_napi/src/input/camera_manager_napi.cpp` **L169–L192**）
**不含** `HIGH_FRAME_RATE`：

```cpp
const std::unordered_map<SceneMode, JsSceneMode> g_nativeToNapiSupportedMode_ = {
    {SceneMode::CAPTURE,  JsSceneMode::JS_CAPTURE},
    {SceneMode::VIDEO,  JsSceneMode::JS_VIDEO},
    {SceneMode::SECURE,  JsSceneMode::JS_SECURE_CAMERA},
};
```

> **`HIGH_FRAME_RATE = 13` 只能由框架自己内部 `SetFeatureMode()` 触发**
> （即 `AdaptOutputVideoHighFrameRate` 检测到 120/240 时），
> **应用无法通过任何公开接口请求它。**

#### 2.4 `getSupportedFrameRatesForVideo` —— 不存在

对 `@ohos.multimedia.camera.d.ts` 全文检索 `getSupportedFrameRatesForVideo`：**命中 0 次**。
该接口在本 SDK 版本（API 24 / HarmonyOS 6.1.1）中**不存在**。

#### 2.5 `CameraFormat` / `CameraMode` 枚举

- **`CameraFormat` 存在**：`.d.ts` **L2552** `enum CameraFormat`，成员是 `RGBA_8888` 等像素格式，
  **没有任何 `HIGH_FPS` 成员**。
- **`CameraMode` 枚举根本不存在**：`.d.ts` 全文检索 `\bCameraMode\b`：**命中 0 次**。
  相机模式只有 `SceneMode`（`.d.ts` **L2493–L2536**）：

```ts
enum SceneMode {
    NORMAL_PHOTO = 1,    // L2507
    NORMAL_VIDEO = 2,    // L2521
    SECURE_PHOTO = 12    // L2535
}
```

> **注意**：这与本任务描述里假设的 `camera.CameraMode.NORMAL_PHOTO` 不同 ——
> **`CameraMode` 不存在，我们用的是 `camera.SceneMode.NORMAL_PHOTO`**（已在真机代码中核实，见第 4 题）。

#### 2.6 HDI 层的 `OperationMode::HIGH_FRAME_RATE`

`drivers_interface` · `camera/v1_3/Types.idl` **L72**：

```idl
    /**
     * Slow motion mode, which dedicated to video recording slow motion
     *
     * @since 5.0
     * @version 1.0
     */
    HIGH_FRAME_RATE = 13,
```

（v1_0 / v1_1 / v1_2 里**都没有**；v1_1/v1_2 最接近的是 `SLOW_MOTION = 6`。
注意注释写的是 *"Slow motion mode"* —— 这个模式的设计意图是**慢动作录制**，不是"预览提速"。）

---

### 第 3 题：NDK / C API 是否提供更多

#### 3.1 本地实际存在的文件

`D:\IDE\DevEco_Studio\sdk\default\openharmony\native\sysroot\usr\include\ohcamera\`
（**目录确实叫 `ohcamera`**）：

| 文件 | 字节 |
|---|---|
| `camera.h` | 29,312 |
| `camera_device.h` | 10,852 |
| `camera_input.h` | 9,935 |
| `camera_manager.h` | 28,425 |
| `capture_session.h` | 81,004 |
| `metadata_output.h` | 7,111 |
| `photo_native.h` | 3,073 |
| `photo_output.h` | 23,908 |
| `preview_output.h` | 13,992 |
| `video_output.h` | 12,114 |

链接库：`native\sysroot\usr\lib\{aarch64-linux-ohos,arm-linux-ohos,x86_64-linux-ohos}\libohcamera.so`。
另有 Doxygen HTML 文档树：`native\docs\html\group___o_h___camera.html`（1.1 MB）、
`struct_camera___frame_rate_range.html` 等。

> **注意**：任务描述里猜测的 `preview_output.h` / `video_output.h` **确实存在**，
> 但**不在 `native\` 根下，而在 `native\sysroot\usr\include\ohcamera\`**。

#### 3.2 帧率相关函数的**确切签名**

`preview_output.h` —— **L245–L299**（doc 注释完整保留）：

```c
/**
 * @brief Get supported preview output frame rate list.
 *
 * @param previewOutput the {@link Camera_PreviewOutput} instance to deliver supported frame rate list.
 * @param frameRateRange the supported {@link Camera_FrameRateRange} list to be filled if the method call succeeds.
 * @param size the size of supported {@link Camera_FrameRateRange} list will be filled.
 * @return {@link #CAMERA_OK} if the method call succeeds.
 *         {@link #CAMERA_INVALID_ARGUMENT} if parameter missing or parameter type incorrect.
 *         {@link #CAMERA_SERVICE_FATAL_ERROR} if camera service fatal error.
 * @since 12
 */
Camera_ErrorCode OH_PreviewOutput_GetSupportedFrameRates(Camera_PreviewOutput* previewOutput,
    Camera_FrameRateRange** frameRateRange, uint32_t* size)
    __attribute__((__availability__(ohos, introduced=12.0.0)));          // L256-258

/**
 * @brief Delete frame rate list.
 * ...
 * @since 12
 */
Camera_ErrorCode OH_PreviewOutput_DeleteFrameRates(Camera_PreviewOutput* previewOutput,
    Camera_FrameRateRange* frameRateRange)                               // L269-271

/**
 * @brief Set preview output frame rate.
 *
 * @param minFps the minimum to be set.
 * @param maxFps the maximum to be set.
 * @return {@link #CAMERA_OK} ... {@link #CAMERA_INVALID_ARGUMENT} ...
 * @since 12
 */
Camera_ErrorCode OH_PreviewOutput_SetFrameRate(Camera_PreviewOutput* previewOutput,
    int32_t minFps, int32_t maxFps)                                      // L283-285

/**
 * @brief Get active preview output frame rate.
 * ...
 * @since 12
 */
Camera_ErrorCode OH_PreviewOutput_GetActiveFrameRate(Camera_PreviewOutput* previewOutput,
    Camera_FrameRateRange* frameRateRange)                               // L297-299
```

`video_output.h` —— **L258–L307**，四个函数**同名同参一一对应**：
`OH_VideoOutput_GetSupportedFrameRates`（**L265**）、`OH_VideoOutput_DeleteFrameRates`（**L278**）、
`OH_VideoOutput_SetFrameRate`（**L292**）、`OH_VideoOutput_GetActiveFrameRate`（**L306**）。

结构体 `camera.h` **L839–L855**：

```c
/**
 * @brief Frame rate range.
 *
 * @since 11
 * @version 1.0
 */
typedef struct Camera_FrameRateRange {
    uint32_t min;    // Min frame rate.
    uint32_t max;    // Max frame rate.
} Camera_FrameRateRange;
```

#### 3.3 NDK **确实**多出来的东西（但与帧率无关）

| 函数 | 位置 | 作用 |
|---|---|---|
| `OH_CameraManager_GetSupportedCameraOutputCapabilityWithSceneMode` | `camera_manager.h` **L233** | 按 SceneMode 查能力（ArkTS 也有） |
| `OH_CameraManager_GetSupportedFullCameraOutputCapabilityWithSceneMode` | `camera_manager.h` **L250** | 查**完整**能力（含被裁剪项） |
| `OH_CameraManager_GetSupportedSceneModes` | `camera_manager.h` **L493** | 枚举支持的 SceneMode |
| `OH_CameraManager_DeleteSceneModes` | `camera_manager.h` **L506** | 释放上者 |
| `OH_CaptureSession_SetSessionMode` | `capture_session.h` **L203** | 设置会话模式 |

但 NDK 的 `Camera_SceneMode` 同样只有三个成员 —— `camera.h` **L160–L180**：

```c
typedef enum Camera_SceneMode {
    NORMAL_PHOTO = 1,     // L169  Normal photo mode.
    NORMAL_VIDEO = 2,     // L174  Normal video mode.
    SECURE_PHOTO = 12     // L179  Secure photo mode.
} Camera_SceneMode;
```

> #### 结论（确证）
> **NDK 的帧率面与 ArkTS 的帧率面是同一套东西** —— 同为 `{GetSupportedFrameRates, DeleteFrameRates,
> SetFrameRate, GetActiveFrameRate}`，同为 `@since 12`，同样的 `min/max` 语义。
> **NDK 在帧率上一点额外能力都没有。**
> NDK 唯一"更多"的是 `GetSupportedFullCameraOutputCapabilityWithSceneMode`（能拿到未被
> 三方裁剪的完整能力表）—— 但它拿到的仍是**同一条 HAL 声明**，不改变兑现与否。
> 另外，`frameworks/native/ndk/impl/capture_session_impl.cpp` 中检索 `FrameRate|frameRate|Fps|fps`：
> **命中 0 次** —— NDK 会话层完全不碰帧率。

---

### 第 4 题：ArkTS 面是否有我们没用的帧率相邻接口

对 `D:\IDE\DevEco_Studio\sdk\default\openharmony\ets\api\@ohos.multimedia.camera.d.ts`（9,605 行）
逐符号穷举结果：

| 符号 | 出现位置（行号） | 说明 |
|---|---|---|
| `FrameRateRange` | **L292, L299**（`@typedef`）；**L304–L341**（`interface`） | `@since 10`，`min`/`max` 均 `readonly` |
| `frameRateRange` | **L363, L371, L377** | 仅 `VideoProfile` 上；`@since 10`，`"Frame rate in unit fps"` |
| `getSupportedFrameRates` | **L7051, L7058, L7063**（PreviewOutput）；**L8659, L8666, L8671**（VideoOutput） | 均 `@since 12` |
| `setFrameRate` | **L7075, L7085**；**L8693** | 均 `@since 12`，抛 `7400101`/`7400110` |
| `getActiveFrameRate` | **L7089, L7096, L7101**；**L8704, L8709** | 均 `@since 12` |
| `getSupportedOutputCapability` | **L709**（`@deprecated since 11`）、**L711**；**L750**（带 `SceneMode`） | L711 已废弃 |
| `getSupportedFullOutputCapability` | **L762** | `@since 12`，`(camera, mode: SceneMode)` |
| `getSupportedSceneModes` | **L730** | `@since 11` |
| `SceneMode` | **L2493–L2536** | 仅 3 成员（见第 2.5 节） |
| `CameraMode` | **无（命中 0 次）** | **该枚举不存在** |
| `PhotoSession` | **L5676–L5710** | `interface PhotoSession extends Session, Flash, ... Aperture` |
| `VideoSession` | **L6058–L6088** | `interface VideoSession extends Session, Flash, ... ControlCenter, Macro` |
| `SecureSession` | **L6703** | |
| `CaptureSession` | **L5035**（整块 `@deprecated since 11`） | |
| `HighResolutionPhotoSession` | **无（命中 0 次）** | 公开 `.d.ts` 中**不存在** |
| `getSupportedFrameRatesForVideo` | **无（命中 0 次）** | **不存在** |
| `isMirrorSupported` | **L7899**（PhotoOutput）、**L8628**（VideoOutput） | `@since 15` |
| `createSession<T extends Session>(mode: SceneMode): T` | **L1113** | `@since 11` |
| `createCaptureSession()` | **L1085** | `@deprecated since 11`，`@useinstead createSession` |

**`@systemapi` 标记**：本 `.d.ts` 中**命中 0 次** —— 即这个文件里**没有任何 systemapi 接口**
（systemapi 的相机接口在另一套 `camera_napi_for_sys` 中，见第 2.3 节 `JsSceneMode` 与
`frameworks/js/camera_napi_for_sys/src/mode/*`，共 17 个系统级 Session，如 `slow_motion_session_napi.cpp`、
`high_res_photo_session_napi.cpp` —— **这些都不在公开 SDK 里**）。

**`@deprecated` 汇总**：`L708`（`createCameraInput` 旧重载）、`L934`、`L1082`（`createCaptureSession`）、
`L1692`、`L5032`–`L5498`（整个 `CaptureSession` 接口块）、`L6893`–`L6924`、`L7933`–`L7944`。

#### 4.1 我们**实际**用的是哪个 session —— 已核实

`C:\Users\26671\lpr-kirin8020-app\LprDemo\entry\src\main\ets\pages\CameraPage.ets` **L667**：

```ts
const sess: camera.PhotoSession = mgr.createSession(camera.SceneMode.NORMAL_PHOTO);
```

**是 `SceneMode.NORMAL_PHOTO`（不是 `CameraMode`，该枚举不存在）。**

相关调用点（行号已于 2026-09-21 对**真机代码树**复核）：
- `L633` `mgr.createPreviewOutput(showProfile, this.surfaceId)` —— 显示路
- `L664` `mgr.createPreviewOutput(analyze, rid)` —— 分析路
- `L638`（显示路，建流后探测） / `L738`（`negotiateFrameRate` 内，遍历 analyze+show）`getSupportedFrameRates()`
- `L768` `outs[i].setFrameRate(lo, hi)`
- `L769` `outs[i].getActiveFrameRate()`
- **`L145` `const WANT_HIGH_FPS: boolean = true;`** —— **高帧率协商是开着的**
- `L179` `const FPS_TARGET: number = 30;`

> ⚠️ **勘误（本轮修正）**：本节初稿读的是 `_hvigor_probe\...` 这份**过期探针副本**，因而写出了
> "`L132 WANT_HIGH_FPS = false`，当前高帧率尝试是关闭的" 与 "`L586`" —— **两条都错**。
> 真机树中该常量为 `true`（L145），且**没有任何 `_hvigor_probe` 目录存在**。
> 需要强调：`WANT_HIGH_FPS = true` **不等于"在请求 60"** —— `FPS_TARGET = 30`，
> `negotiateFrameRate` 会挑**包含 30 的那个区间**（即 `1-30`）再 `setFrameRate(30,30)`。
> 所以"高帧率尝试关闭"这个说法**双重错误**：协商本就开着，且目标本就是 30。
> 本节的**结论不受影响**（结论来自 `preview_output.cpp` 源码，与端侧常量无关）。

且 `L130–L131` 的注释已经踩到了正确认知：

> 实测建流前 PreviewOutput.getSupportedFrameRates() 返回空数组，
> 必须在 session.start() 之后查（API 文档：during session running）。

这与源码完全吻合：`GetSupportedFrameRates()` 第一行就要 `GetSession()`，
没有 session 直接 `return {}`（`preview_output.cpp` **L490–L491**）。

#### 4.2 `getActiveFrameRate()` 为什么"报 60 却只有 30"—— 代码级解释

`frameworks/js/camera_napi/src/output/preview_output_napi.cpp` **L863–L886**：

```cpp
napi_value PreviewOutputNapi::GetActiveFrameRate(napi_env env, napi_callback_info info)
{
    ...
    std::vector<int32_t> frameRateRange = previewOutputNapi->previewOutput_->GetFrameRateRange();
    CameraNapiUtils::CreateFrameRateJSArray(env, frameRateRange, result);
```

而 `GetFrameRateRange()` 是（`preview_output.cpp` **L435–L438**）：

```cpp
const std::vector<int32_t>& PreviewOutput::GetFrameRateRange()
{
    return previewFrameRateRange_;      // ← 本地缓存，只在 SetFrameRateRange() 里被写
}
```

`previewFrameRateRange_` 的**唯一写入点**是 `SetFrameRateRange()`（**L440–L445**），
而它只在 `SetFrameRate()`（**L459–L485**）成功下发后被调用。

> #### 结论（确证）
> **`getActiveFrameRate()` 返回的是"我们上次设置成功的值"，是框架的本地记录，
> 与传感器实际出帧率毫无关系。**
> 之前笔记里说的"`active=60-60` 是个陷阱"是**对的**，而且现在有代码级根因：
> 它压根不是一次测量，只是一次回读。

---

### 第 5 题：session 类型 / mode 与可用帧率的关系

#### 5.1 两个 Session 都允许 `setFrameRate`，实现**逐字相同**

`frameworks/native/camera/base/src/session/photo_session.cpp` **L278–L281**：

```cpp
bool PhotoSession::CanSetFrameRateRange(int32_t minFps, int32_t maxFps, CaptureOutput* curOutput)
{
    return CanSetFrameRateRangeForOutput(minFps, maxFps, curOutput) ? true : false;
}
```

`frameworks/native/camera/base/src/session/video_session.cpp` **L301–L304**：

```cpp
bool VideoSession::CanSetFrameRateRange(int32_t minFps, int32_t maxFps, CaptureOutput* curOutput)
{
    return CanSetFrameRateRangeForOutput(minFps, maxFps, curOutput) ? true : false;
}
```

基类 `CaptureSession` 则是**一律拒绝**（`capture_session.cpp` **L3362–L3369**）：

```cpp
bool CaptureSession::CanSetFrameRateRange(int32_t minFps, int32_t maxFps, CaptureOutput* curOutput)
{
    MEDIA_WARNING_LOG("CaptureSession::CanSetFrameRateRange can not set frame rate range for %{public}d mode",
                      GetMode());
    return false;
}
```

→ **`PhotoSession` 与 `VideoSession` 对帧率的态度完全一致，没有任何一方更宽松。**
这也印证了官方文档 `arkts-apis-camera-PreviewOutput.md` **L242–L243** 的说法（两种模式都支持）。

#### 5.2 真正的差别：**查的是哪一套 Profile 集合**

- `PhotoSession` 用 `SceneMode::CAPTURE` 的能力集：`photo_session.cpp` **L229**
  `device->modePhotoProfiles_.find(SceneMode::CAPTURE)`、**L243** `modePreviewProfiles_.find(SceneMode::CAPTURE)`。
- `VideoSession` 用 `SceneMode::VIDEO`：`video_session.cpp` **L240 / L254 / L266**。
- `VideoOutput::GetSupportedFrameRates()` **硬编码** `SceneMode::VIDEO`
  （`video_output.cpp` **L327**），不看会话实际模式。

而 `PreviewOutput::GetSupportedFrameRates()` 用的是 **`session->GetMode()`**（`preview_output.cpp` **L494**）。

**两套预配置的默认帧率不同**（这可能是"换 VideoSession 会看到不同数字"的来源）：

| Session | 预配置默认 fps | 出处 |
|---|---|---|
| PhotoSession | `{ .fixedFps = 30, .minFps = 12, .maxFps = 30 }` | `photo_session.cpp` **L40, 47, 54, 62, 84, 91, 98, 106, 128, 135, 142, 150** |
| VideoSession | `{ .fixedFps = 30, .minFps = 24, .maxFps = 30 }` | `video_session.cpp` **L36, 43, 50, 58, 82, 89, 96, 104, 128, 135, 142, 150** |

（这只是**预配置模板**的默认值，不是 `getSupportedFrameRates()` 的返回值；
后者来自 HAL 解析出的 `modePreviewProfiles_[mode]`。）

#### 5.3 官方文档的说法

`zh-cn/application-dev/reference/apis-camera-kit/arkts-apis-camera-VideoSession.md` **L13**：

> 默认的视频录制模式，适用于一般场景。支持720P、1080p等多种分辨率的录制，
> **可选择不同帧率（如30fps、60fps）**。

这是**全仓唯一一处**官方文档把 60fps 与具体 Session 挂钩的表述 ——
**而且它挂在 `VideoSession` 上**。这是支持"换 VideoSession 试试"的最强官方依据。

但反面证据同样硬：

1. 设备在 `NORMAL_PHOTO` 下**已经**报出 `60-60`（第 6 题证明这是按 mode 查出来的），
   说明 60 并非 `NORMAL_VIDEO` 独有。
2. `setFrameRate` 在两种模式下**都**允许（5.1 节，代码级）。
3. 观测到的失败模式是"**被接受但不兑现**"，这是 HAL/传感器行为，
   **换 mode 不改变 HAL 是否兑现**。
4. `camera-recording.md` **L137–L141** 的约束（预览流与录像流帧率必须一致/成约数）
   在我们的场景里**不适用** —— 我们**根本没有 VideoOutput**（`CameraPage.ets` 只有两条
   `createPreviewOutput`），所以那条约束链不会被触发。

> #### 结论（推断）
> 换 `VideoSession` 会让我们**看到另一套 Profile 列表**（很可能不同，甚至可能更宽），
> 因此**值得花 30 分钟实测一次**。但基于源码，它**没有任何机制能让 HAL 兑现 60**。
> **期望值：低。** 判定标准见第七节路径 A。

---

### 第 6 题：`60-60` 是否是 profile 专属的

#### 6.1 是。而且是**逐 output 精确匹配**

`preview_output.cpp` **L504–L512**（第 1.3 节已完整引用）：

```cpp
supportedProfiles.erase(std::remove_if(
    supportedProfiles.begin(), supportedProfiles.end(),
    [&](Profile& profile) {
        return profile.format_ != previewFormat_ ||                    // ← 格式
               profile.GetSize().height != previewSize_.height ||      // ← 高
               profile.GetSize().width  != previewSize_.width;         // ← 宽
    }), supportedProfiles.end());
...
std::vector<int32_t> supportedFrameRatesItem = {item.fps_.minFps, item.fps_.maxFps};
```

`previewFormat_` / `previewSize_` 由 `SetOutputFormat()`（**L447–L451**）与 `SetSize()`（**L453–L457**）写入，
即**这条 PreviewOutput 绑定的那个 Profile**。

`VideoOutput` 同理（`video_output.cpp` **L330–L339**，按 `videoFormat_` / `videoSize_` 过滤后取
`item.GetFrameRates()`）。

> #### 结论（确证）
> **`getSupportedFrameRates()` 是"输出"的属性，不是"设备"的属性。**
> 两条绑定不同 Profile 的 PreviewOutput（我们的 `show` 960×960 与 `analyze` 640×480）
> **完全可能返回不同的帧率列表**。
> 所以"设备报 `[1-30, 60-60]`"这句话**不严谨** —— 准确说法是
> "**在那个 format+分辨率的 profile 上**，HAL 声明了 `1-30` 与 `60-60` 两条区间"。

#### 6.2 `fps_` 从哪来 —— HAL 元数据

`frameworks/native/camera/base/src/input/camera_manager.cpp`

**L2582–L2588**（ProfileLevel 路径）：

```cpp
for (const auto &detailInfo : streamInfo.detailInfos) {
    CameraFormat format = getCameraFormat(static_cast<camera_format_t>(detailInfo.format));
    if (format == CAMERA_FORMAT_INVALID) { continue; }
    Size size{detailInfo.width, detailInfo.height};
    Fps fps{detailInfo.fixedFps, detailInfo.minFps, detailInfo.maxFps};   // ← L2588 直接来自元数据
```

**L2772–L2773**（ExtendConfig 路径）：

```cpp
Fps fps { static_cast<uint32_t>(detailInfo.fixedFps), static_cast<uint32_t>(detailInfo.minFps),
    static_cast<uint32_t>(detailInfo.maxFps) };
```

**L2436–L2445**（Basic 路径，走 `OHOS_ABILITY_FPS_RANGES` 标签）：

```cpp
camera_metadata_item_t fpsItem;
int ret = Camera::FindCameraMetadataItem(metadata->get(), OHOS_ABILITY_FPS_RANGES, &fpsItem);
if (ret != CAM_META_SUCCESS) { continue; }
for (uint32_t j = 0; j < (fpsItem.count - 1); j += FPS_STEP) {
    std::vector<int32_t> fps = { fpsItem.data.i32[j], fpsItem.data.i32[j + 1] };
    VideoProfile vidProfile = VideoProfile(format, size, fps);
    profilesWrapper.vidProfiles.push_back(vidProfile);
}
```

`Profile::DumpProfile`（`camera_output_capability.cpp` **L78–L85**）把这个值打进日志，
**是我们在真机上能拿到的直接证据**：

```cpp
MEDIA_DEBUG_LOG("%{public}s format : %{public}d, width: %{public}d, height: %{public}d, "
                "support ability: %{public}s, fixedFps: %{public}d, minFps: %{public}d, maxFps: %{public}d",
                name.c_str(), format_, size_.width, size_.height, abilityIdStr.c_str(),
                fps_.fixedFps, fps_.minFps, fps_.maxFps);
```

**`GetSupportedOutputCapability(camera, mode)` 就是按 mode 从 `CameraDevice` 取缓存** ——
`camera_manager.cpp` **L2636–L2656**：

```cpp
sptr<CameraOutputCapability> CameraManager::GetSupportedOutputCapability(sptr<CameraDevice>& cameraDevice,
    int32_t modeName)
{
    ...
    cameraOutputCapability->SetPhotoProfiles(camera->modePhotoProfiles_[modeName]);      // L2651
    cameraOutputCapability->SetPreviewProfiles(camera->modePreviewProfiles_[modeName]);  // L2652
    if (!isPhotoMode_.count(modeName)) {
        cameraOutputCapability->SetVideoProfiles(camera->modeVideoProfiles_[modeName]);  // L2654
    }
    cameraOutputCapability->SetDepthProfiles(camera->modeDepthProfiles_[modeName]);      // L2656
```

**框架全程没有计算、没有钳位、没有推断** —— 只是把 HAL 解析出来的
`modePreviewProfiles_[mode]` 原样交出去。

#### 6.3 钳位在哪：`setMaxFps` 不在 OpenHarmony 里

对已下载的 OpenHarmony 相机框架全部 `.cpp` / `.h` 检索 `setMaxFps`：**命中 0 次**。

设备日志里的 `CameraDaemon/IPS_STREAMIMG: Misc.cpp:4026 setMaxFps()` 属于
**华为厂商闭源相机 daemon**（`CameraDaemon` / `IPS_STREAMIMG` 都不是 OpenHarmony 的进程名或模块名）。
OpenHarmony 框架把 `OHOS_CONTROL_FPS_RANGES` 写进 `changedMetadata_` 下发
（`capture_session.cpp` **L3334–L3358**）：

```cpp
int32_t CaptureSession::SetFrameRateRange(const std::vector<int32_t>& frameRateRange)
{
    std::vector<int32_t> videoFrameRateRange = frameRateRange;
    this->LockForControl();
    bool isSuccess = this->changedMetadata_->addEntry(
        OHOS_CONTROL_FPS_RANGES, videoFrameRateRange.data(), videoFrameRateRange.size());   // ← L3338
    ...
    for (size_t i = 0; i < frameRateRange.size(); i++) {
        if (frameRateRange[i] > CONTROL_CENTER_FPS_MAX) {    // ← L3351  CONTROL_CENTER_FPS_MAX = 30
            frameCondition = false;
        }
    }
    CameraManager::GetInstance()->SetControlCenterFrameCondition(frameCondition);            // ← L3355
```

**注意 L3351**：框架对 >30 的帧率只有一个动作 —— 把控制中心的"帧率条件"标记为 false
（一个 UI/策略提示），**并不阻止下发**。这解释了为什么 `setFrameRate(60,60)` 不抛异常。

> #### 结论（推断，但推理链完整）
> 1. HAL 通过元数据声明了 `1-30` 与 `60-60`（第 6.2 节，代码级）。
> 2. 框架原样透传，不校验、不钳位（第 6.2 节 + `setMaxFps` 命中 0）。
> 3. 框架把 `OHOS_CONTROL_FPS_RANGES = {60,60}` 下发到 HDI（`capture_session.cpp` L3338）。
> 4. 厂商 daemon 收到后，由 `setMaxFps()` 把它按自己的预算压回 30/27/25/20
>    （设备日志，`Misc.cpp:4026`）。
> 5. 框架**从不回读实际帧率**，所以 `getActiveFrameRate()` 依旧报 60-60（第 4.2 节，代码级）。
>
> **即：声明 60 的是 HAL，兑现不了 60 的也是 HAL，框架在中间什么都没做。**

---

## 三、对本项目的可行路径（按性价比排序）

| # | 路径 | 预期解锁 >30 fps 的概率 | 确认/证伪所需证据 | 备注 |
|---|---|---|---|---|
| **A** | **换 `SceneMode.NORMAL_VIDEO`（VideoSession）跑一次 A/B** | **10–15%（推断）** | ① `getSupportedFrameRates()` 返回的列表**是否与 NORMAL_PHOTO 不同**；② 若列表含 >30 的区间，实测 arrive fps 是否 >30。**若列表完全相同 → 直接证伪，成本 30 分钟** | 唯一有官方文档背书的路径（`VideoSession.md` L13 明说"30fps、60fps"）。但源码显示它不改变 HAL 兑现行为。**建议做，但按"排除法"做，不要抱期望** |
| **B** | **把 `WANT_HIGH_FPS` 打开、并用 `GetSupportedFullCameraOutputCapabilityWithSceneMode` 或日志 dump 全部 profile 的 `fps_`** | **0%（这不是提速手段，是诊断）** | 拿到每个 profile 的 `fixedFps/minFps/maxFps` 三元组。**若 `60-60` 只出现在某个低分辨率 profile 上**，说明 HAL 的 60 档位是特定 profile 专属的；**若 `60-60` 的 `fixedFps` 字段为 0 而 min/max 都是 60**，那更能说明它是一条"标称"而非"实配"档位 | **强烈建议先做这个**，它把后续所有猜测变成可判定的。见下方"如何拿日志" |
| **C** | **接受 30 fps，把到达率贴死 30** | **100%（已验证）** | 已有：全 NPU 档 30.00 fps ±0.3（`camera-fps-ceiling.md` L15） | 唯一被实测支持的路径。**注意 `camera-fps-ceiling.md` 第六节的警告：全 NPU 档读错参考图** —— 该档只能用于性能上限测量 |
| **D** | **走 NDK / `OH_PreviewOutput_SetFrameRate`** | **0%（已证伪）** | 第 3 题：NDK 与 ArkTS 帧率面逐函数一一对应 | **死路，不要再试** |
| **E** | **找 `CameraMode.HIGH_FPS` / `SceneMode.HIGH_FRAME_RATE` / `HighResolutionPhotoSession`** | **0%（已证伪）** | 第 2.5 / 第 4 题：`CameraMode` 不存在；`HIGH_FRAME_RATE` 只在内部枚举且**仅由 120/240 触发**；`HighResolutionPhotoSession` 不在公开 SDK | **死路。** 且注意 `HIGH_FRAME_RATE` 的设计意图是**慢动作录制**（HDI 注释 *"Slow motion mode"*），不是预览提速 |
| **F** | **设 `setFrameRate(60,60)` 再试（任何分辨率）** | **0%（已多次证伪）** | 已有实测：`active=60-60` 但 arrive ~29.8（`camera-fps-ceiling.md` L69） | **死路。** 根因已在第 4.2 节代码级定位：`getActiveFrameRate` 只是回读，不是测量 |
| **G** | **给会话加一条 `VideoOutput` 并把帧率设成与预览一致** | **<5%（推断）** | `camera-recording.md` L139 说"录像流已设置过范围帧率时，预览流帧率必须设置与其相同的范围帧率" —— 但这只是**一致性约束**，不是提速手段 | **基本死路。** 加 VideoOutput 只会多一条流抢带宽，`camera-fps-ceiling.md` L140–L145 已证伪"双流互抢"是瓶颈 |
| **H** | **换亮场景重测（怀疑 `mCurMaxFps` 是曝光/热预算）** | **可能把 20 → 30，但拿不到 60** | 日志里 `mCurMaxFps` 有 `0→27`、`27→25`、`25→20`、`20→30` 四种走向，**说明它是动态量**。~~`camera-fps-ceiling.md` L143–L144 已观察到暗场景 30→15 砍半换曝光~~ ⚠️ **该引用是悬空的**（2026-09-21 核实：`camera-fps-ceiling.md` L143–144 讲的是检测器落点读错，且全文无 `15 fps` / `30→15`）——**「30→15 砍半换曝光」这条观察在本仓库找不到出处**，引用前须先补证据 | **不是 60fps 路径**，但对**稳定拿到 30** 有价值。建议在论文里把 `mCurMaxFps` 作为"传感器侧动态预算"的证据记录 |
| **I** | **联系厂商 / 提单要 60fps 支持** | 未知 | 需厂商确认该 SKU 的 60fps 档位是"标称能力"还是"可交付能力" | 本仓库无法完成。**若论文需要 60fps 结论，这是唯一可能改变结论的路径** |

### 如何拿日志做路径 B（具体做法）

框架在解析每个 Profile 时会打 `DumpProfile`（`camera_output_capability.cpp` L78–L85），
格式为：

```
preview format : %d, width: %d, height: %d, support ability: %s, fixedFps: %d, minFps: %d, maxFps: %d
```

这是 **DEBUG 级**日志（`MEDIA_DEBUG_LOG`）。建议：

```bash
# 提高相机域日志级别，抓 Profile 解析
hdc shell hilog -b D -D 0xD003F00   # camera domain
hdc shell hilog | Select-String "fixedFps"
```

或在应用侧直接 dump（无需 root）：

```ts
const cap = mgr.getSupportedOutputCapability(device, camera.SceneMode.NORMAL_PHOTO);
for (const p of cap.previewProfiles) {
  hilog.info(DOMAIN, TAG, 'PROFILE %{public}dx%{public}d fmt=%{public}d',
    p.size.width, p.size.height, p.format);
}
// 注意：ArkTS 的 Profile 接口不带 fps 字段（只有 VideoProfile.frameRateRange 有），
// 所以 fps_ 只能靠 hilog 的 DumpProfile，或对每条 profile 建 output 后调 getSupportedFrameRates()。
```

> **⚠️ 重要限制**：ArkTS 的 `Profile` 接口（`.d.ts` **L287** 只暴露 `readonly size: Size`）
> **不暴露 `fps_`**。`frameRateRange` 只挂在 `VideoProfile`（`.d.ts` **L377**）上。
> 所以"逐 profile 的帧率"在 ArkTS 侧**只能**通过 `getSupportedFrameRates()`（即建 output 后问）
> 或 hilog 的 `DumpProfile` 拿到。

---

## 四、边界与未验证

### 4.1 无法获取的（硬边界）

1. **厂商闭源 HAL / daemon 源码**。`CameraDaemon`、`IPS_STREAMIMG`、`Misc.cpp:4026 setMaxFps()`
   都不在 OpenHarmony 仓库中（已对全仓 grep `setMaxFps`：命中 0）。
   **"谁在钳位"是从框架侧排除 + 日志侧印证得出的推断，不是读到了钳位代码。**
   若要变成"确证"，需要厂商提供 HAL 源码或符号，或做逆向 —— 本仓库不做逆向（同 ADR-0003 的边界立场）。
2. **设备上 `60-60` 那条 profile 的确切三元组**（`fixedFps` / `minFps` / `maxFps`）。
   需要路径 B 的真机 hilog。**在拿到之前，无法判断 `60-60` 是"标称能力"还是"实配档位"。**
3. **`NORMAL_VIDEO` 下 `getSupportedFrameRates()` 的实际返回**。推断依据是源码的 mode 分派，
   未在真机上比对过两套列表。
4. **本 SKU 的 HAL 是否实现了 `OperationMode::HIGH_FRAME_RATE = 13`**。无法从设备外验证。
5. **`docs.openharmony.cn` 的 HTML 页面**：`.../v5.0/.../arkts-apis-camera-PreviewOutput.md`
   与 `.../v5.1/...` 均返回 **HTTP 404**。因此全部文档证据改用
   **官方文档仓库 `openharmony/docs` 的 raw markdown**（同一来源，更权威、可引用行号）。
   `developer.huawei.com` 的 HarmonyOS 文档页未尝试（JS 渲染，raw 不可得）。
6. **`web_search` 工具不可用**：本会话中该工具返回
   `DeepSeek API error (HTTP 402): Insufficient Balance`。
   **因此所有网络证据均来自"直接 web_fetch 官方 gitee raw 文件"，没有经过任何搜索索引。**
   这是一条方法论限制：**我无法保证没有遗漏其他官方页面**，只能保证**引用的每一条都可追溯**。

### 4.2 未验证的推断（明确标注）

| 推断 | 依据 | 如何证伪 |
|---|---|---|
| 钳位发生在厂商 daemon 的 `setMaxFps()` | 框架侧 `setMaxFps` 命中 0；框架不校验不复查 | 拿到 daemon 源码/符号 |
| `mCurMaxFps` 是动态曝光/热预算 | 日志有 `0→27`、`27→25`、`25→20`、`20→30` 四种走向；~~`camera-fps-ceiling.md` L143–L144 暗场景 30→15~~ ⚠️ **该引用悬空**（2026-09-21 核实，见上表 H 行） | 控制光照/温度做 A/B |
| 换 VideoSession 会看到不同 profile 列表 | `preview_output.cpp` L494 用 `session->GetMode()`；`camera_manager.cpp` L2651–L2656 按 mode 取缓存 | 真机 A/B（路径 A） |
| 60fps 档位是"标称"而非"实配" | `setMaxFps` 从不把上限抬到 30 以上 | 路径 B 的 hilog |

### 4.3 版本口径说明

本文引用的 OpenHarmony 源码全部取自 **`master` 分支**（`raw.giteeusercontent.com/.../raw/master/...`）。
设备是 **HarmonyOS 6.1.1 / API 24**（本地 SDK `sdk-pkg.json` 自述 `platformVersion 6.1.1`）。
**`master` 可能领先于 API 24 对应的发布分支**，因此个别行号/实现细节在 6.1.1 上可能略有差异。
本文所有**结论**都建立在多处互证之上（API 文档 + 源码 + 设备日志），
不依赖任何单一函数的精确行号。若要逐字复核，请以 `OpenHarmony-6.0-Release` 或
对应 6.1.x 分支为准。

### 4.4 与既有笔记的关系

- `camera-fps-ceiling.md` 的实测结论（**"请求 60 不被兑现"**）**被本轮完全证实**，
  且新增了**代码级根因**：`getActiveFrameRate()` 是本地回读（第 4.2 节），
  框架对帧率**零校验、零复查**（第 1.3 / 6.3 节）。
- `camera-fps-ceiling.md` 里"`active=60-60` 是个陷阱"的说法**正确且现在有解释**。
- **未推翻任何既有结论**。本轮是给"为什么"补上了源码层证据链。
- **对本项目论文的建议表述**（诚实版）：

  > 设备 HAL 通过 `getSupportedFrameRates()` 向应用声明了 `60-60` 档位，
  > OpenHarmony 相机框架对该声明**只做包含性校验、不做可达性验证、且从不回读实际帧率**；
  > 因此 `setFrameRate(60,60)` 被接受、`getActiveFrameRate()` 回报 `60-60`，
  > 而传感器实际交付恒为 ~30 fps。钳位点位于厂商闭源相机 daemon
  > （`CameraDaemon/IPS_STREAMIMG` 的 `setMaxFps()`，该符号不存在于 OpenHarmony 源码中）。

### 4.5 【2026-09-21 补充】本地 `HuaweiDocs` 语料复核 + 一条新约束

后续一轮（`camera-npu-headroom.md`）在本地官方语料
`C:\Users\26671\Desktop\HuaweiDocs\cn`（8877 篇 `.md`，与线上同源）上复核了本文第 1c 题，
并**新发现一条与本文相关的官方约束**：

- **第 1c 题的直接复核（不是转述）**：本地 SDK
  `openharmony\ets\api\@ohos.multimedia.camera.d.ts` 的 `enum SceneMode`（L2493）
  **只有 3 个成员**：`NORMAL_PHOTO=1` / `NORMAL_VIDEO=2` / `SECURE_PHOTO=12`；
  对 `HIGH_FRAME|HIGH_SPEED|SLOW_MOTION` 全文检索 **0 命中**。
  → 本文「`HIGH_FRAME_RATE` 未对三方开放」的结论**得到 SDK 文件级确证**。
- **新约束（本文未覆盖）**：`camera-framerate.md:98-99` 与
  `camera-setframerate-native.md:116-117` 规定 ——
  设**非固定**帧率后**不支持再次调用** `setFrameRate`；
  设**固定**帧率后可以重设，但**新旧帧率必须互相整除**。
  我们设的是 `30-30`（固定帧率），故受此约束。
  本文第 4 节测「30 → 60」时该方向可整除（60/30=2）所以合法；
  但**「60 → 30 → 60」这类反复横跳、以及不重开会话的动态调档从未验证**。
  本轮切档协议每档都重开会话，故不受影响；**将来做动态调档前必须先验这条。**

  > **因此本项目在 30 fps 处取相机侧上限，且该上限的成因不在应用可控范围内。**
