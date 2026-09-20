# Note · 无人值守自动化在手机侧不可实现；读屏可做，注入点击不可

> 本文件原为 `ADR-0009`，2026-09-20 移出 ADR 系列。原因有两条：它记录的是**可行性结论**而非决策（缺"真实取舍"），且其原头部自述「前置：无（独立于 LPR 主线）」——它不属于本项目的决策系列。内容完整保留。

## 问题

曾有一个诉求：让手机自动完成「读取屏幕 → 决策 → 注入点击」的闭环（例如自动领取某视频 App 的金币），且要求**全自动无人值守、纯手机、不插电脑**。

这个闭环在 HarmonyOS 6.1 上是否可实现？

## 结论

**在手机上不可实现。读屏可做，注入点击不可做。全自动闭环只能走 PC 在环。**

三堵**互相独立**的墙：

| # | 墙 | 依据 |
|---|---|---|
| 1 | ArkTS 注入是系统接口 | `inputEventClient.injectTouchEvent` 需 `ohos.permission.INJECT_INPUT_EVENT`（system_basic），普通应用调用返回 **err 202** |
| 2 | C 注入限定设备类型 | `OH_Input_InjectTouchEvent` 需 `ohos.permission.CONTROL_DEVICE`（system_basic），文档原文「该接口在 **PC/2in1** 设备中可正常调用，**在其他设备上调用无效果**」 |
| 3 | 无障碍通道被主动关闭 | `getWindowRootElement` / `onAccessibilityEvent` / `performAction('click')` / `injectGestureSync` 自 **API 12 起全部废弃**，原文「**系统不再开放相关能力**」 |

第三堵最关键：那正是 Android `AccessibilityService` 的洞，**华为明确焊死了**——所有 Android 自动点击器都靠它活着。

**Root 也不是出路**：Kirin 990 及以后的 bootloader 状态被列为「无解」，且华为在系统更新/降级时**重新上锁**；无 HarmonyOS 版 Magisk/KernelSU。

## 可行的形态

| 形态 | 可行性 |
|---|---|
| **PC 在环（唯一全自动）** | ✅ PC 跑 `hdc shell uitest uiInput click <x> <y>` + `hdc shell uitest dumpLayout`。代价：每个语义动作需重新 dump UI 树，延迟数百 ms 量级 |
| **设备侧只读** | ✅ `screenshot.capture()` 需 `ohos.permission.CUSTOM_SCREEN_CAPTURE`（**normal 级、user_grant、面向所有应用开放**，Phone 自 API 21 起）；连续录制走 `AVScreenCaptureRecorder`（无系统权限，每次会话需 Picker 同意） |
| **辅助模式（人点）** | ✅ 设备侧识别并高亮，人来点。注意全局悬浮窗需 ACL `SYSTEM_FLOAT_WINDOW`（**仅调试签名可用，不可上架**） |
| **仅当自己的应用在前台** | ✅ `@ohos.uitest` 可在自己的 ohosTest/Hypium 内驱动自身。对驱动别的 App 无用 |

现成骨架（**全部是 PC 在环**）：`codematrixer/hmdriver2`（443★，`hdc fport` 到设备侧 uitest 服务）、`ziguiway/hmnextauto`、`mao026/hon-cli`。**没有任何一个做设备侧免 PC 的跨应用自动点击**——这个"没有"本身就是结论。

## 后台执行：另一个独立限制

`TASK_KEEPING`（唯一通用的"持续计算"长时任务类型）在**手机上不可用**——需 `KEEP_BACKGROUND_RUNNING_SYSTEM`（system_basic）或 PC/2in1。其余长时任务类型（`DATA_TRANSFER` / `AUDIO_PLAYBACK` / `LOCATION` 等）都要求**匹配的真实业务行为**，系统会审计并挂起不匹配的声明。短时任务上限 10 分钟/天、单次 3 分钟。

**且系统会主动杀负载**：`SystemLoadLevel` 有 8 档，官方要求 HIGH(3) 起「停止所有无感服务」、OVERHEATED(4)/WARNING(5)「降级主要前台服务」、EMERGENCY(6)「除基础用途外停止所有服务」。**持续推理循环正是它设计要杀掉的对象。**

## 影响

- 该诉求**搁置**（用户已确认：LPR First，自动化后续再议）。
- 若日后启动：设计必须是 **PC 在环**（手机做识别+决策，PC 做注入），且手机侧仍可跑 NPU 推理——**这不影响"榨干硬件"的目标**。
- 论文与简历中**禁止**出现"纯手机全自动操作其他应用"的表述。

## 边界

- 本笔记的"PC/2in1 限定"来自**文档原文**，未在 nova 14 Pro 真机上验证是否硬性运行时门禁（文档措辞是「调用无效果」）。若要推翻，需真机实验。
- 本笔记 **不**排除通过企业/合作伙伴签名或系统应用身份实现；但那不是个人开发者路径。
- 自动化目标 App 的 ToS 风险**未评估**——即使技术可行，也可能违反服务条款。

## 待办

1. 若启动自动化线：用 `hmdriver2` 搭 PC 在环最小闭环，测单动作延迟。
2. 真机验证 `OH_Input_InjectTouchEvent` 在手机上是否确实无效（可推翻本笔记的边界）。
