# T3 · 相机实时：任务派发器丢任务

- **日期**：2026-09-21
- **票**：#6
- **对应 ADR**：ADR-0003（落点自证）、ADR-0004（单后端 MS Lite）
- **数据**：`evidence/t3_camera_throughput.log`（在 app 仓库）

## 现象

相机页长期显示「档位加载失败」，**相机流从未启动**，因此 T3 的吞吐指标一直
是空的（「丢帧 0 / 0 帧到达」）。票面因此挂着 `ready-for-human`。

## 定位

补上诊断日志后拿到关键事实：`loadModelAsync` 三次调用**全部返回空串**
（`rawlen det=0 rec=0 cls=0`），而 native 侧**一条 `loadModel` 日志都没有**
—— 说明请求根本没走到模型加载器。

根因在 `InferenceRunner`（`napi_init.cpp`）：它用**单个任务槽**而不是队列。

```
Submit:  task_ = fn; has_ = true; notify; wait(!has_)
Loop:    取 task_; 执行; has_ = false; notify_all
```

两个并发 Submit 时：

1. 第二个覆盖 `task_`，而 `has_` 已经是 `true`
2. 第一个跑完把 `has_` 置 `false` 并 `notify_all`
3. **两个提交者都被唤醒**，但第二个的任务从未执行
4. 第二个的 `job->kv` 保持空串 → Promise 静默 resolve 成 `""`

**触发条件是跨页面并发提交**：相机页 `ensureSessions` 加载模型的同一时刻，
首页的自动探针仍在后台提交任务。同页面内的串行 `await` 不会碰撞，所以这个
缺陷在只用一个页面时永远不出现。

## 修法

`std::deque<std::shared_ptr<Item>>`，每个任务自带 `finished` 标志与**自己的**
condition_variable —— 唤醒只针对该任务，不存在「唤醒错人」。任务仍在锁外执行，
推理期间不挡入队。

## 真机验证

```
STREAM START show=960x960 analyze=640x480 rot=90
FIRST FRAME kind=NV21 decode=11 infer=1896 rot=90
FRAME n=60  fps=3.65  plate=赣AD38888 split=6|1
RATE arrive=3.39 fps done=3.39 fps dropped_in_win=0 cum_arrived=85  cum_done=85
RATE arrive=3.76 fps done=3.76 fps dropped_in_win=0 cum_arrived=130 cum_done=130
```

累计 **130 帧到达 / 130 帧完成 / 0 丢帧**，实时读出真实车牌 `赣AD38888`（8 字符）。

到达率 ≈ 完成率 ≈ **3.4 fps**（生产档，640×480 分析流）。两者相等说明
**生产档下流水线比相机出帧快**，这一档测到的是相机侧速率，不是流水线上限 ——
要测流水线上限得换「基准档」或「全 NPU 档」。

## 落点面板在相机页是实测值

```
det    LANDED=CPU  (req=cpu)  l2=1062.5495
rec  ⚡LANDED=NNRT:NPU_ohos.boot.hardware.kirin8020_v2_0  (req=nnrt)  l2=4.0489
```

`det.l2=1062.5495` 与相册页的 `1076.7692` **不同** → 证明确为实时观测，
不是 UI 复读相册页的值（ADR-0003 的要求）。

## 一条反复出现的模式：**错误信息把真因抹掉**

本轮顺带修掉两个观测缺陷，它们与 T2 的两个「字段名承诺的语义与实际不符」
属同一类 —— **不是崩溃或错值，而是诊断信息本身失真**，于是问题被隐藏得更深：

| 缺陷 | 后果 |
|---|---|
| `ensureSessions` 在 `ctx` 为 `undefined` 时静默 `return false`，而调用方 `applyGear` **无条件**把 status 覆盖成「档位加载失败」 | 现场只剩四个字，拿不到真因 |
| 模型加载失败只记 `LOAD FAIL`，不记各角色的 `ok`/`err` | 无法区分「raw 为空」与「raw 有内容但没有 ok 键」 |

两者都**只能靠观测才能发现**，且都不影响正确性 —— 只影响可诊断性。
本项目已有三处同类（T2 两处 + 此处两处），值得在写新代码时当成一条纪律：
**泛化兜底文案不得覆盖具体原因。**

## 边界

- 本修复解决「模型加载被丢」，**不解决**相机在暗场景把帧率砍半换曝光
  （30→15）的传感器行为 —— 那是既有结论，与本缺陷无关。
- 3.4 fps 是**当前场景**（室内、暗）的实测值，不是设备上限。
- 一图多牌：相机页实测每帧只有 1 张牌，多牌渲染未验证。
