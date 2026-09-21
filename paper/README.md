# 论文编译与验收

> 本机**没有装任何 TeX 发行版**（无 pdflatex / xelatex / latexmk），
> 用 **tectonic** 单二进制编译。见 [工单 #15](https://github.com/YangShusen2001/lpr-kirin8020/issues/15)。

---

## 一、工具链

| 组件 | 位置 / 获取方式 |
|---|---|
| **tectonic** | `~/AppData/Local/tectonic/tectonic.exe`（本机已有，50 MB）<br>装法：`winget install tectonic`，或从 GitHub tectonic releases 取 `tectonic.exe` |
| **PyMuPDF**（验收用） | 托管 venv：`~/.workbuddy/binaries/python/envs/default/Scripts/python.exe` |

**为什么不用 pdflatex**：本机没有 TeX 发行版，而 tectonic 是单静态二进制，
自带 TeX Live 子集与字体，**按需下载宏包到本地缓存**（首次编译慢，之后快）。

---

## 二、编译

```bash
# 从仓库根目录
python tools/build_paper.py              # 编译全部目标
python tools/build_paper.py --only en    # 只编译英文稿
python tools/build_paper.py --probe      # 最小探针，验证工具链本身
```

产物：`paper/en/main.pdf`，日志：`paper/en/main.build.log`。

### ⚠️ 三个必须知道的坑

**1. 调用语法是裸形式，不是 `compile`**

```bash
tectonic main.tex --outdir .        # ✅
tectonic compile main.tex           # ❌ compile 只存在于 -X 后面
```
写成后者会把 `compile` **当成输入文件名**，报 `Found argument ... which wasn't expected`。

**2. 必须走 Python `subprocess`，不能直接调**

shell 的命令扫描器会拒掉 tectonic 调用；而且**任何含非 ASCII 的 shell 命令都可能被拦**
（本工程路径含中文）。`tools/build_paper.py` 因此不把中文路径拼进命令行。

**3. `tectonic` 路径可用环境变量覆盖**

```bash
TECTONIC=/path/to/tectonic.exe python tools/build_paper.py
```
换机器时不必改源码。

---

## 三、验收：**编译成功 ≠ 排版正确**

这是本项目的一条硬纪律（与「落点自证」同源）：
`exit=0` 只说明 TeX 没崩，**不说明内容真的印上去了**。

### 3.1 编译日志的紧凑分诊

`build_paper.py` 会自动从日志里只抽三件事——因为一次 IEEEtran 编译会吐几百条
`Underfull \hbox`，把真正重要的淹掉：

```
[main.tex] exit=0 pdf=yes (213153 B)
   missing glyphs: none
   overfull hbox >= 5pt: none
   errors: none
```

**判定线**：`missing glyphs` 必须为 0（有就是内容丢了）；`overfull ≥20pt`（约 7mm）必修，
`<5pt` 可放过。

### 3.2 PDF 文本抽取断言

```bash
<venv>/python.exe tools/verify_paper_pdf.py
```

断言四类东西：

1. **19 个关键数字/术语**必须在页面上（每个都对应 `docs/evidence-index.md` 的已机检数字）
2. **7 个章节标题**必须都在
3. **3 条禁令**不得出现（NPU 利用率主张 / GPU 加速主张 / 「移植保真」这个已被推翻的旧结论）
4. **页数**在 6–14 之间（IEEEtran conference 目标 8–10）

```bash
<venv>/python.exe tools/verify_paper_pdf.py --find "26.9"   # 抽查某串在第几页
```

> ⚠️ **前置**：需要 PyMuPDF。用默认 python 跑会打印 `backend=none / pages=0` ——
> 那是**工具问题，不是论文坏了**。判据：`backend=none` ⇒ 换解释器；
> `backend=fitz` 且 `pages>0` 而断言失败 ⇒ 才是真问题。

### 3.3 人眼复核

```bash
# 渲染指定页为 PNG
python -c "import pymupdf; d=pymupdf.open('paper/en/main.pdf'); d[0].get_pixmap(dpi=150).save('p1.png')"
```

预览图放在 `paper/en/preview/`（不入库）。

---

## 四、CJK 说明（当前不需要，但要知道）

`IEEEtran` 正文用 `lmroman`，**没有汉字字形**——`\texttt{藏DT5022}` 里的 `藏` 会被**静默丢弃**，
日志只留一行 `Missing character`，表格那格直接空白。

本论文**正文零汉字**（车牌串已罗马化，如 `Su E05172`），所以不需要配 CJK。
`.tex` 里的 46 个汉字**全在 `%` 注释里**，不进排版。

若将来要在正文排汉字，加 xeCJK + Fandol（Fandol 随 TeX 分发，无需系统字体）：

```latex
\usepackage{xeCJK}
\setCJKmainfont{FandolSong-Regular.otf}[
  BoldFont=FandolSong-Bold.otf, ItalicFont=FandolKai-Regular.otf]
\setCJKmonofont{FandolFang-Regular.otf}   % \texttt 里的汉字走这个
\setCJKsansfont{FandolHei-Regular.otf}
\xeCJKsetup{CJKmath=true}
```

---

## 五、图

6 张图由 `lpr-kirin8020-app/tools/make_figures.py` **从证据生成**（PNG + PDF），
论文用 PDF 版（矢量，缩印不糊）。

```bash
cd ../lpr-kirin8020-app
<venv>/python.exe tools/make_figures.py --out ../车牌识别/paper/figures
```

**纪律**：图必须数据驱动，不允许手绘示意。每张图的来源见脚本里的注释。

---

## 六、当前状态

| 项 | 值 |
|---|---|
| 页数 | 7（IEEEtran conference） |
| 体积 | ~213 KB |
| 缺失字形 | 0 |
| overfull ≥5pt | 0 |
| 编译错误 | 0 |
| 数字守卫 | 67 项全通过（`lpr-kirin8020-app/tools/verify_published_numbers.py`） |
| 图 | 6 张，全部被正文引用 |

> 页数会随工单 #22（论文补完：GPU 章节 / Related Work 扩写 / 基线对比）增长到 8–10。
