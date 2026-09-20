# ADR-0008 · 工具链与源码全部在磁盘上；CANN 侧可做真机对撞

- **状态**：已接受（本 ADR 更正了一次搜索结论）
- **日期**：2026-09-20
- **前置**：ADR-0001（继承）、ADR-0004（后端选择）
- **证据**：`C:\Users\26671\lpr-harmony\`（1.7 GB / 13630 文件）；`omg_conv/ddk/`；`omg_conv/out/*.om`

## 问题

前期工作认为 App 源码（`lpr-harmony/`）与 CANN DDK（`omg_conv/ddk/`）已丢失，因此 ADR-0001 决定"代码全部重写"、ADR-0004 计划退化为"文档级对撞"。

**这两条前提都是错的。**

## 决策

**源码、工具链、模型产物全部在磁盘上，无需重新获取；CANN 侧的真机逐算子对撞可以做。**

实际位置（`C:\Users\26671\lpr-harmony\`，**不在 `Desktop` 下**）：

| 类别 | 内容 |
|---|---|
| App 源码 | `LprDemo/entry/src/main/cpp/`：`ms_engine.cpp` 650 行、`lpr_pipeline.cpp` 1084 行、`napi_init.cpp` 1082 行、`ncnn_engine.cpp` 532 行、`nnrt_probe.cpp` 446 行、`vulkan_probe.cpp` 252 行 |
| ArkTS | `ets/pages/Index.ets` 1320 行、`CameraPage.ets` 1099 行 |
| CANN DDK | `omg_conv/ddk/tools/{tools_omg,tools_dopt,tools_ascendc,platform}`（822 MB）；`tools_omg/master/omg`（ELF64）；`platform/kirin9020/` |
| `.om` 产物 | `omg_conv/out/`：`om_rec.om` 5.04 MB、`om_det.om` 1.95 MB、`om_dethead.om`、`om_cls.om`、`om_lprnet.om`、`om_lprnet_npufix.om` |
| `.ms` 产物 | `LprDemo/.../rawfile/models/`：15 个，含 fp16/fp32 双档、`lprnet`/`lprnet_npufix`、`y5fu` 的 dec/head/s1/s1r4 变体 |
| ncnn 产物 | `.ncnn.param` + `.ncnn.bin`（rec/cls/dethead） |
| 转换脚本 | `omg_conv/convert.sh`、`convert_one.sh` |
| 构建文档 | `README.md`（hvigor 环境变量、`DEVECO_SDK_HOME` 陷阱、签名约束）、`LprDemo/AGENT.md` |

DDK 的 OMG 调用（`convert.sh` 实现，A12 记录）：
```
bash ddk/tools/tools_omg/omg --model X.onnx --framework 5 --output out/om_X \
     --platform kirin9020 --input_shape <name>:1,3,H,W
```

## 理由

1. **DDK 无需申请**。官方 `DDK-tools-next-6.1.1.0`（252 MiB）在 CDN 上**匿名可下**，无登录、无实名、无企业认证。`omg` 是 64 位 Linux ELF，**需 WSL**；Windows 的 OMG 在 `100.600.010.010` 已被华为删除。
2. **`.om` 与源 ONNX 的 SHA256 逐字节对应**，即产物就是这三个模型的，不是客人模型。ADR-013 的"缺口=OMG"已闭合。
3. **源码完整且无损坏**。`lpr_pipeline.cpp` 1084 行；注意 `lpr_pipeline.cpp.yolov8_backup` 与 `lpr_pipeline_new_v2.cpp` 是 A18 §5 记录的**遗留物**，主文件的手工合并从未完成——改端侧前先 `assembleHap` 干跑一次编译。
4. **App 无需从零写**。ADR-0001 的"代码全部重写"仍成立（用户明确要求重开发），但**基线是这份可编译的真实源码，不是丢失的备份**。

## 后果

- ADR-0004 的"文档级对撞"升级为**真机逐算子对撞**：把 `ShusenPaper/app` 的 50 个算子模型各转一份 `.om`，与 `.ms` 版本在真机上同输入对撞。
- **CANN 转换链已于 2026-09-20 实测复现**（`_scratch/convert_om_real.sh`）：三个生产模型全部重新转出，`rc=0`，magic 均为 `IMOD`（`49 4d 4f 44`），**字节数与 09-18 原件完全一致**（cls 841728 / dethead 1010950 / rec 5041253）。SHA256 不同——`.om` 内嵌时间戳与路径元数据，**尺寸一致才是可比证据**。
- 生产 `.ms` 转换链无需华为账号：`converter_lite.exe` 2.6.0 在 `D:\Tools\mindspore-lite\mindspore-lite-2.6.0-win-x64\tools\converter\converter\`，三个模型已实测转换成功且 SHA256 与项目自带 `.ms` 一致。

## OMG 的四个真实陷阱（全部实测踩到）

1. **入口必须是包装脚本** `tools_omg/omg`，不是 `tools_omg/master/omg`。包装脚本自己设 `LD_LIBRARY_PATH` / `CCE_LIB_DIR` / loader 软链。直接跑二进制会报 `libomg.so not found` 或 unknown flag。
2. **输出路径不能含非 ASCII 字符**。`--output=.../车牌识别/_scratch/...` 被拒：`failed validation of new value ... for flag 'output'` + `CheckOutputPathValid ... false`。与 hvigor 拒绝非 ASCII 工程路径（`00306003`）**同一类缺陷**。必须用纯 ASCII 输出路径。
3. **不要传 `--target=omc`**。那会生成 `.omc` 中间产物而非 `.om`（实测产出了 3 个 `.omc` 却无 `.om`，`rc=0` 静默成功）。
4. **版本参数是 `--hiai_version`，不是 `--omg_version`**。传后者会 `unknown command line flag` 然后**静默不出模型**。

另：`te_fusion` / `librl_search.so` / `libai_npucore_generated.so` 的加载失败是**噪声**（JIT-only 回退），不影响产出——09-18 的成功日志里同样有这些行。

## 边界声明

- 本 ADR **不**主张 `.om` 优于 `.ms`：已有实测是 MS Lite 在识别器上更快（3.99 vs 5.19 ms），CANN 的价值在**算子覆盖对照面**（166 IR 算子 vs NNRT 的 58/198 且全 FP16）。
- 本 ADR **不**主张 OMG 与设备 CANN 版本一定匹配：设备侧 `108.631.120.010` 与 DDK 的版本对应规则**无官方文档**（华为在 5.0.1.0 删除了版本↔芯片匹配表）。首次转换须以 `compat=` / `build_rc=` / `run_rc=` 三关实测为准。**本次只验证了 PC 侧转换，未在设备上跑新产的 `.om`。**
  - 2026-09-20 真机探针：`hdc shell param get const.hiai.vendor.hiaiversion` 返回 **`fail! errNum is:1002`**（参数不存在）。官方文档称该命令可用，但**在 USB 连接的非 2in1 设备上取不到**——版本对齐只能走 CANN Kit 的 `HMS_HiAI_GetVersion` 应用内 API。设备确认：`MIA-AL00`、API 24、`SystemCapability.AI.NeuralNetworkRuntime=true`，且 `com.shusen.lprdemo` 与 `com.shusen.npubench` **两个 App 都还装着**。
- 本 ADR **不**主张 `lpr-harmony` 的代码可直接复用为生产基线：它是 09-20 状态，含已知的实验档与遗留文件。

## 更正记录

**2026-09-20 首次更正**。本 ADR 的前身结论是"App 源码全盘搜不到、DDK 也丢了、只能退化为文档级对撞"。该结论基于一次**范围不完整的搜索**——只扫了 `C:\Users\26671\Desktop`、`D:\`、`C:\Users\26671\Downloads`，**漏掉了用户主目录 `C:\Users\26671\` 本身**，而工程恰好在 `C:\Users\26671\lpr-harmony\`。

教训与 ADR-015 同构：**"没搜到"不等于"不存在"**。声明一个资产丢失前，必须先穷尽搜索路径并写明搜索范围。

## 未完成动作

1. 修复 WSL 启动（内存），跑一次 OMG 转换验证三关。
2. 把 `ShusenPaper/app` 的算子套件转成 `.om`，做逐算子对撞。
3. 清点 `lpr-harmony` 中哪些文件属于"实验档/遗留物"，建立可信基线清单。
