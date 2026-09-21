# 数字一致性表（evidence index）

> **本文件是论文 / 简历 / 个人网页三处数字的唯一来源。**
> 任何出口要引用一个数字，必须能在下表找到它，且表中每一行都能指向一个真实存在的证据文件。
>
> 配套守卫：`lpr-kirin8020-app/tools/verify_published_numbers.py`
> —— 它把下表里可机检的项**从原始证据重算一遍**，对不上就退出码 1。
> **守卫不过，不许发布任何数字。**

---

## 0. 三条硬规则

1. **禁止 NPU 利用率数字。** 该平台物理上不暴露（应用侧与 `hdc` 侧都没有计数器），
   依据与边界见 `docs/adr/0003-evidence-standard-latency-delta-and-landing.md`。
   允许的替代形态只有三个：**落点**（`req=` / `LANDED=` / `fallback=`）、
   **延迟差**、**张量指纹**。
2. **每个数字必须带条件。** 至少要有：样本量 n、热档（thermal）、构建模式（release/debug）、
   同栈内还是跨栈。缺条件的数字**不可比**。
3. **跨栈比较只当量级参考。** NPU 走 MindSpore Lite + NNRT，GPU 只有 ncnn-Vulkan，
   CPU 有 ms-cpu 与 ncnn-cpu 两套。任何跑分表必须带「框架」列
   （ADR-0002 后果第二条）。

### 更新流程

```bash
cd <REPO>/lpr-kirin8020-app
python tools/verify_published_numbers.py            # 全部检查
python tools/verify_published_numbers.py --list     # 只查证据文件是否存在
python tools/verify_published_numbers.py --rq4 evidence/rq4_thermal_80r.csv
```

改了证据文件（重跑探针）之后，**先跑守卫，再改本表**，不要反过来。

---

## 1. 落点与准确性（RQ3 主线）

| # | 数字 | 条件 | 证据 | 守卫项 |
|---|---|---|---|---|
| 1.1 | 端侧 NPU 裸识别 **89.9%**（899/1000） | 裁剪图裸喂识别器，release，同栈 MS Lite | `evidence/crop_bare.log` | ✅ |
| 1.2 | 端侧 CPU 裸识别 **86.7%**（867/1000） | 同上，唯一变量是后端 | `evidence/crop_bare.log` | ✅ |
| 1.3 | 主机 onnxruntime rpv3 **90.6%**（906/1000） | **前期工作**（lpr-showcase A16），T14 现场重跑核对一致 | `lpr-showcase/tools/lprnet_real_accuracy.py` | 需重跑 |
| 1.4 | 端侧 NPU vs 主机：**−0.7 pp，配对 McNemar p=0.0156（0:7）** | 同一批 1000 张图，配对消共同方差 | `tools/mcnemar_device_vs_host.py` | 需重跑 |
| 1.5 | 端侧 NPU vs 端侧 CPU：**+3.2 pp，p<0.0001（38:6）** | 同 C++ 预处理、同模型文件 ⇒ **纯后端差异** | `tools/mcnemar_triplet.py` | 需重跑 |
| 1.6 | 端侧 CPU vs 主机：**−3.9 pp，p<0.0001（0:39）** | 后端 + 预处理两层 | `tools/mcnemar_triplet.py` | 需重跑 |
| 1.7 | 配对严格嵌套：**主机 ⊃ NPU ⊃ CPU** | 端侧在 0 张图上赢过主机 | T14 表 | — |
| 1.8 | 真实整车场景 det 落点分歧 **0.1%**（1/1000） | CCPD1000，720×1160，release | `evidence/ccpd_scene.log` | ✅ |
| 1.9 | 真实整车场景 rec 落点分歧 **0%**（0/1000） | 同一批图，同探针参数化 | `evidence/ccpd_scene_rec.log` | ✅ |
| 1.10 | 真实整车场景全流水线准确率 **99.1%**（991/1000） | 7 字符，det/rec 两侧相同 | `evidence/ccpd_scene.log` | ✅ |
| 1.11 | 8 字符新能源牌准确率 **92.5%**（925/1000） | CCPD-Green，**皖占 60%**（偏斜无法消除） | `evidence/scene_green_rec.log` | ✅ |
| 1.12 | 牌长代价 **−6.6 pp**（99.1% → 92.5%） | 逐省对照已排除省份构成（5 省方向一致） | T13 §5 | — |
| 1.13 | 8 字符落点分歧 **0.1%**（1/1000） | 与 7 字符的 0% 同量级 | `evidence/scene_green_rec.log` | ✅ |
| 1.14 | 省份位占替换错误 **33/67 = 49.3%** | 等长行 n=971 | `evidence/scene_green_rec.log` | ✅ |
| 1.15 | 8 字符长度错误 **29/1000 = 2.9%** | 典型形态是少一位 | `evidence/scene_green_rec.log` | ✅ |

**1.14 的跨工况一致性**（这是「省份位是识别器/数据集属性，与后端无关」的证据）：
T11 裁剪图裸喂 75/77 · T12 真实场景 9 张里 5 张 · T13 8 字符 33/67 —— 三个工况、两种牌长。

## 2. 算子覆盖边界（C2）

| # | 数字 | 条件 | 证据 | 守卫项 |
|---|---|---|---|---|
| 2.1 | CANN 侧 **51/51 全部通过**（compat=0 / construct=ok / build_rc=0 / run_rc=0） | 真机 nova 14 Pro，`--platform=kirin9020` 转换 | `models_om_ops/op_collide.csv` | ✅ |
| 2.2 | 含 NNRT 侧被拒的 **9 个**算子 | relu/sigmoid/softmax/maxpool/pad/cast_f16/transpose/resize/tanh | 同上 | ✅ |
| 2.3 | `convtranspose`：NNRT 侧**连模型都产不出来**，CANN 侧跑通 | `converter_lite 2.6.0` 形状推断失败 | 同上 + T8 | ✅ |
| 2.4 | NNRT 通路：独立可编译 **20/36**，被拒 **16/36** | **前期工作**（ShusenPaper L1 矩阵） | `shusen-npu-characterization/results/week3-op-matrix.md` | — |

> ⚠️ 2.1 只证明**准入边界**，**不证明 CANN 更快**。生产档实测 MS Lite 在识别器上更快
> （rec 3.99 vs 5.19 ms）。且 `.om` 侧每条只跑 3 次、无热身，**延迟只可排序不可引用**。

## 3. 性能与热特性（RQ4）

| # | 数字 | 条件 | 证据 | 守卫项 |
|---|---|---|---|---|
| 3.1 | 识别器 NPU vs CPU **4.46×**（mean 口径） | 同栈 MS Lite；n=961/993（非空子集） | `evidence/crop_bare.log` | ✅ |
| 3.2 | 识别器耗时 mean：CPU **16.78 ms** / NPU **3.76 ms** | 同上；**口径见下方更正说明** | `evidence/crop_bare.log` | ✅ |
| 3.3 | 识别器长度错误：CPU **50**（5.0%）/ NPU **17**（1.7%） | 同一批 1000 张 | `evidence/crop_bare.log` | ✅ |
| 3.4 | RQ4 端到端（80 轮）p50 **73.9 ms** / mean **75.76 ms** / max 150.3 ms | 23.30 min，thermal 恒 2，充电中 | `evidence/rq4_thermal_80r.csv` | ✅ |
| 3.5 | **持续负载退化 +26.9%**（r0–17 → r36–53），**热档不变** | 已排除一次系统冻结；CPU 侧 +29.3% / NPU 侧 +19.2% | `evidence/rq4_thermal_80r.csv` | ✅ |
| 3.6 | 张量指纹逐轮恒定：`det.l2` / `rec.l2` / `code` 各只有 1 个取值 | 证明后端计算路径未退化 | `evidence/rq4_thermal*.csv` | ✅ |
| 3.7 | **thermal 2→3 台阶在 23.3 分钟内未被触发** | 80/80 轮恒为 2 —— 负结果，须如实报告 | `evidence/rq4_thermal_80r.csv` | ✅ |

> ⚠️ **禁止引用「CPU 侧方差大于 NPU 侧」或「两侧基本相等」。**
> 三次测量给出三个不同答案（`-O0` CPU 大 / 25 轮相等 / 80 轮 NPU 大），
> 且单次运行内 NPU 侧 CV 在 8.8%–48.2% 之间摆动。**这个比较本身不稳定。**
> 可支持的只有「轮间方差很大，CV 约 27%」。详见 `docs/notes/t7-rq4-thermal.md`。

### 3.1 RQ4 三批采集的条件对照（**引用前必读**）

| 数据集 | 轮数 | 时长 | 构建 | thermal | 电池 ℃ | 充电 | 说明 |
|---|---|---|---|---|---|---|---|
| `rq4_thermal_o0_superseded.csv` | 20 | ~5 min | **`-O0`** | 2 | 35–36 | 是 | 已作废，仅作对照 |
| `rq4_thermal.csv` | 25 | ~6 min | `-O2` | **1** | 33–34 | 否 | T7 首版 |
| `rq4_thermal_80r.csv` | **80** | **23.30 min** | `-O2` | **2** | 34–35 | 是 | 2026-09-21 补跑（本文引用的是这一批） |
| ~~`rq4_thermal_release.csv`~~ | 25 | — | `-O2` | 1 | 33–34 | 否 | **已删除** —— 与 `rq4_thermal.csv` 逐字节相同 |

> **为什么补跑**：25 轮版全程 `thermal=1`，**从未跨过 thermal 2→3 的台阶**，
> 所以 RQ4 的核心问题（持续负载下 NPU 收益能否维持）**没有被测到**。
> 补跑把它变成一个 23 分钟的实验结论：**台阶仍未触发，但延迟照样上升 26.9%**。
>
> **两次运行都在 `thermal=2 + 充电中`**（`-O0` 旧数据也是这个条件），
> 于是「构建模式」这个变量第一次可以被单独隔离出来。
>
> **一次未计划的复跑被中止**：原打算跑第二轮做复现，用户判断第一轮 80 轮已足够而叫停。
> 因此本文的 RQ4 结论是**单次运行**，没有独立复现 —— 引用时须一起说。

## 4. 相机路与调度（应用级案例）

| # | 数字 | 条件 | 证据 | 守卫项 |
|---|---|---|---|---|
| 4.1 | 生产档（det=CPU）检出帧 frame p50 **40.0 ms**，余量 **−6.7 ms** | 640×480，thermal 4，sweep1 gear0 | `evidence/camera_windows.csv` / `camera_summary.md` | — |
| 4.2 | 全 NPU 档检出帧 frame p50 **28.0 ms**，余量 **+5.3 ms** | 同上条件 | 同上 | — |
| 4.3 | 检测段占帧预算 **49.0%**（19.61 ms）vs 识别段 **10.0%**（3.98 ms） | 生产档检出帧 40 ms 的分解 | `camera-npu-headroom.md` §3.2 | — |
| 4.4 | 相机只取帧上限 **29.99 fps**（NORMAL_PHOTO）/ **49.98 fps**（NORMAL_VIDEO+VideoOutput 60-60） | 两套会话配置，**不可互相代入** | `camera_summary.md` + T9 | — |
| 4.5 | 60fps 供给下产能：生产 **36.18** / 全 NPU **43.55** fps | 被背压，`arrive` 不是相机读数 | `evidence/camera_t9ab.log` | — |
| 4.6 | **隔离基准 7.4 ms vs 流水线内 19.5–31.6 ms**（约 2×） | 同模型同后端同线程数 | `evidence/camera_gap_sweep.log` | — |
| 4.7 | C8 定位 = **DVFS + 线程池唤醒**两个叠加机理 | 剂量-反应 + 忙等对照 + 线程数对照三步 | `camera-npu-headroom.md` §3.2c.2 | — |
| 4.8 | 检测段线程数 `t4` 最优（7.49 ms），`t6`/`t8` 更差 | **负结果**，默认值已最优 | `evidence/camera_thread_sweep.log` | — |

## 5. 禁止发布的数字

| 禁止项 | 原因 |
|---|---|
| 任何 NPU 利用率 / 占用率 / 负载百分比 | 平台不暴露，写了无法验证（ADR-0003） |
| 「GPU 加速 N 倍」 | 实测三个模型在 Vulkan 上都比 CPU 慢；GPU 那格只能写「通路成立且数值保真」 |
| 「移植保真」（指准确率） | 已被 T14 推翻：端侧比主机低 0.7 pp 且统计显著 |
| 「检测器才是敏感环节」 | 已被 T12 推翻：那是裁剪图工况的产物（真实场景 0.1%） |
| `1000/p50(frameMs)` 称作 fps | 那是**服务时间倒数**，不是帧率（`CONTEXT.md`） |
| 「CANN 全通过 ⇒ CANN 更快」 | 只证明准入边界 |
| 「融合携带」说成因果 | 目前是相关性，未做同权重逐算子插桩对照 |

## 6. 继承自前期工作的数字（**必须显式标注，不得与新增重复计数**）

ADR-0001 后果第一条要求。以下数字**不是本工程测的**：

| 数字 | 来源 | 位置 |
|---|---|---|
| L1 算子矩阵 36 算子三信号 | ShusenPaper | `results/week3-op-matrix.md` |
| L2 套件 5 轮 × 21 模型；ResNet-50 **13.11×**、MobileNetV2 INT8 **0.89×** | ShusenPaper | `results/week2-aggregate.md` |
| Roofline 实测峰值 **1.56 TFLOPS** FP16 | ShusenPaper | `paper/figures/roofline.*` |
| 三缺陷提单链（其一获华为官方确认） | ShusenPaper | 工单往返包 |
| 主机 onnxruntime **90.6%** | lpr-showcase A16 | `tools/lprnet_real_accuracy.py` |
| 1000 张真值裁剪集（文件名即真值） | lpr-showcase | `_dataset/real/crops/` |
| 三个 ONNX 模型、77 项字符表 | lpr-showcase | `assets/models/` |
| FP16 缓冲区被声明为 FP32 的 dtype 缺陷（误差 7.78e18% → 0.015%） | lpr-showcase ADR-003 | `docs/adr/ADR-003` |

> ⚠️ **`ShusenPaper` 的 checksum 校验发现过两处 FAIL**（`native_decode_tail`、`yolov8n` 原版）。
> 复用前须确认所用子集已通过校验。

---

## 7. 2026-09-21 建立本表时发现的错误（已就地更正）

建立这张表的过程本身抓到了 6 处「文档与证据不符」。全部已改，并纳入守卫：

| # | 位置 | 原写 | 实际 | 性质 |
|---|---|---|---|---|
| 1 | `t11` 表格 + 结论 + 分层表 | CPU 识别耗时 **16.12 ms** | **16.78 ms** | **数字不可复现** —— 任何口径（全量/去首行/仅 ok=1/配对/中位数/截尾）都算不出 16.12 |
| 2 | `t11` 同上 | 加速比 **4.32×** | **4.46×** | 由 #1 传导 |
| 3 | `t13` 正文 | 替换错误总数 **66**、占比 **50%** | **67**、**49.3%** | **正文与自己的表矛盾** —— 该表 `[33,2,7,11,5,1,4,4]` 合计就是 67 |
| 4 | `t10` 证据行 | `evidence/crop_ab_rec.log` | `evidence/crop_ab.log` | **文件不存在**，rec 轮用的是另一个文件名 |
| 5 | `t8` 数据行 | `op_collide.csv` / `op_collide.json` | `models_om_ops/op_collide.csv` + `op_collide_device.log` | **json 不存在**，且路径缺 `models_om_ops/` 前缀 |
| 6 | `t7` 展示表（更早已修） | 只列 12 行却标称 25 轮 | 补全 25 行 | 数字对、表漏极值 |

**这次发现的分布值得注意**：准确率类数字（899/867/49/38/6/17/50/925/999/991）
**全部可复现**；出问题的是**顺手取均值**（#1/#2）和**正文与表格分头维护**（#3）。
⇒ 结论：**逐位比对出来的数字比"统计量"可靠；表格与正文必须同源。**

守卫脚本 `tools/verify_published_numbers.py` 就是为这两条建的：
声明值必须能被重算（治 #1/#2），表格里的数字必须来自同一处（治 #3）。
