# native 代码曾长期以 -O0 编译（未优化）

**发现时间**：2026-09-21（T3 相机帧率偏低排查）
**影响范围**：**所有** native 延迟 / 帧率数字，包括 T7 的 RQ4 热特性 20 轮数据
**是否影响正确性**：否 —— 落点、`l2` 指纹、识别结果在 `-O0`/`-O2` 下逐位相同（已实测）

## 症状

相机页帧率约 **7 fps**，而「基准档」（只取帧、不做任何推理）能到 **20 fps**。
两者相差近 3 倍，且生产档 `arrive == done`、`dropped = 0` —— 说明相机没有被
我们拖住（相机能给 20），但一经推理就掉到 7。看起来像「算法太慢」。

## 根因：两个 `-O` 参数，后者胜出

`entry/build-profile.json5` 里确实写了：

```json5
"externalNativeOptions": {
  "cppFlags": "-O3",          // 看起来已经开了优化
}
```

但 hvigor 默认按 **debug** 构建，CMake 因 `CMAKE_BUILD_TYPE=Debug` 追加自己的
`-O0 -g`，位置在 `-O3` **之后**。gcc/clang 取**最后一个** `-O` 参数，于是
`-O3` 被静默废掉。`build.ninja` 里的真实 FLAGS：

```
-fdata-sections ... -O3 -D__MUSL__ -O0 -g -fPIC
                   ^^^            ^^^
                   被废掉          实际生效
```

**没有任何报错、警告或日志。** 唯一的后果是全部 native 代码未优化运行。

## 真机实测

同一台 nova 14 Pro、同一场景、同一档位（生产档），只改构建模式：

| 指标 | `-O0`（默认 debug） | `-O2`（`buildMode=release`） |
|---|---|---|
| 相机帧率（生产档） | **7 fps** | **20 fps** |
| `conv`（NV21→RGBA + rot90） | ~25 ms | **1.42 ms** |
| native 单帧合计 | ~86 ms | ~20 ms |
| 基准档（只取帧） | 20 fps | 20 fps |

修好后三档（生产 / 全 NPU / 基准）**都是 20 fps** —— 流水线不再是瓶颈，
受限于相机出帧率本身。

**交叉佐证**：主机端 `-O2` 微基准（`bench_conv.cpp`，同样的像素数学与循环结构）
测出 `conv` = **1.412 ms**，与真机 `-O2` 的 `1.42 ms` 同量级。两个独立平台一致，
说明 1.42 ms 才是这段代码的真实成本，25 ms 是 `-O0` 的产物。

## 一个被证伪的假设

我最初怀疑 `rot=90` 时目标写入散射（内层循环沿 x 递增 → `dy=x` 每步跳一整行
1920 B → 每像素命中新 cache line）。微基准**证伪**了它：

```
A 现状   rot=90 行优先（散射写）   1.412 ms
B 对照   rot=0  行优先（连续写）   1.353 ms   <- 只差 4%
C 候选   rot=90 分块 16x16         1.812 ms   <- 更慢
```

散射代价仅 **4%**，而 16×16 分块反而**变慢** 28%（分块破坏了顺序预取）。
所以这段代码的循环结构本来就是对的 —— **不需要为它做任何算法优化**，
它唯一的病是编译没开优化。这次微基准的价值就在于**阻止了一次无用的重写**。

## 修法

构建时必须显式指定 release：

```powershell
cd <REPO>/lpr-kirin8020-app\LprDemo
$env:JAVA_HOME='<JBR>'
$env:PATH='<JBR>\bin;' + $env:PATH
$env:DEVECO_SDK_HOME='<SDK>'
Remove-Item Env:\NODE_OPTIONS -ErrorAction SilentlyContinue
& '<HVIGOR>\bin\hvigorw.bat' --mode module `
    -p product=default -p buildMode=release assembleHap --no-daemon
```

**注意产物路径相同**（`entry/build/default/outputs/default/entry-default-signed.hap`），
debug/release 会互相覆盖 —— 装完要确认用的是哪个。

## 守卫

`tools/check_native_build_flags.py` 直接读 hvigor 生成的 `build.ninja`，
取**最后一个** `-O` 参数并断言它不是 `-O0`（同时检查 `NDEBUG`）：

```
$ python tools/check_native_build_flags.py
[FAIL] debug    生效 -O0      NDEBUG=无   ...\.cxx\...\debug\arm64-v8a\build.ninja
```

**引用任何 native 延迟 / 帧率数字之前，先跑这个守卫。** 它不需要设备。

## 对本项目已有结论的影响

| 结论 | 是否受影响 |
|---|---|
| 落点自证（`LANDED=`）、`l2` 指纹 | **不受影响** —— `-O0`/`-O2` 下逐位相同（实测） |
| 识别正确性（`苏ED5172`、`绿牌`、置信度 `0.7273/0.7366`） | **不受影响**（实测一致） |
| T8 CANN 算子对撞 51/51 | **不受影响** —— 那是准入判定，不是延迟 |
| T7 RQ4 的**绝对**延迟（p50 139.5 ms 等） | **失效** —— 含 `-O0` 膨胀，须重测 |
| T7 RQ4 的**相对**结构（CPU 侧 CV 20.8% vs NPU 侧 13.2%） | **待重测确认** —— 方差来源可能随优化改变 |
| 「CPU 侧 vs NPU 侧」的**拆分归属** | **待重测确认** —— `tRecogMs` 含 NNRT 宿主侧前后处理，优化后占比会变 |

RQ4 的绝对值与方差结构需要**在 release 构建上重跑**才能重新引用。
在这之前，T7 数据只能作为「`-O0` 下的观测」引用，且必须标注构建模式。
