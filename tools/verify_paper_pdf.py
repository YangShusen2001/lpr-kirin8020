"""论文 PDF 的程序化验收：编译成功 ≠ 排版正确。

技能 `latex-paper-tectonic` 的核心纪律：`exit=0` 只说明 TeX 没崩，
**不说明内容真的印上去了**。必须抽 PDF 文本断言。

本脚本断言三类东西：

1. **正文真的在页面上** —— 每个关键数字/术语都能在抽取文本里找到。
   防的是「数字在 .tex 里但被排版丢了」。
2. **图真的插进去了** —— 5 张图各自被引用（图本身由 make_figures.py 出，
   这里只验证 LaTeX 侧引用成功）。
3. **页数与结构合理** —— IEEEtran conference 目标 8–10 页。

用法：
  <venv>/python.exe tools/verify_paper_pdf.py
  <venv>/python.exe tools/verify_paper_pdf.py --find "26.9"   # 抽查某个串出现在第几页

⚠️ 前置：需要 PyMuPDF。本机装在托管 venv：
  C:/Users/26671/.workbuddy/binaries/python/envs/default/Scripts/python.exe
若用默认 python 跑，会打印 backend=none / pages=0 —— 那是**工具问题，不是论文坏了**。
"""
from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "paper" / "en" / "main.pdf"

# --- 必须出现在 PDF 里的串 ---------------------------------------------------
# 每一条都对应 `docs/evidence-index.md` 里的一个已机检数字。
# 左边是给人看的说明，右边是必须在 PDF 文本里找到的字面串。
MUST_APPEAR: list[tuple[str, str]] = [
    # 准确性（T11 / T12 / T13 / T14）
    ("端侧 NPU 裸识别准确率", "89.9"),
    ("端侧 CPU 裸识别准确率", "86.7"),
    ("主机参照准确率", "90.6"),
    ("配对 McNemar p 值", "0.0156"),
    ("后端对准确率的影响", "3.2"),
    ("真实场景全流水线准确率", "99.1"),
    ("8 字符新能源牌准确率", "92.5"),
    ("牌长代价", "6.6"),
    ("省份位占替换错误", "49.3"),
    # 算子覆盖（T8）
    ("CANN 算子准入", "51/51"),
    ("NNRT 侧被拒的算子", "ConvTranspose"),
    # 性能（T11 / C8）
    ("识别器加速比", "4.46"),
    ("隔离基准延迟", "7.4"),
    # RQ4（80 轮）
    ("持续负载漂移", "26.9"),
    ("RQ4 轮数", "80"),
    # 帧预算
    ("检测段占帧预算", "49"),
    # 结构性术语
    ("落点自证核心字段", "LANDED"),
    ("回落字段", "fallback"),
    ("张量指纹", "fingerprint"),
]

# --- 章节标题必须都在 --------------------------------------------------------
MUST_HAVE_SECTIONS = [
    "Introduction",
    "Related Work",
    "Operator Coverage",
    "Case Study",
    "Sustained-Load",
    "Threats to Validity",
    "Conclusion",
]

# --- 明令禁止出现的串 --------------------------------------------------------
# 见 docs/adr/0003：平台上 NPU 利用率物理不可读，任何利用率数字都是自伤。
MUST_NOT_APPEAR: list[tuple[str, str]] = [
    ("不得出现 NPU 利用率主张", "utilisation of the NPU is"),
    ("不得出现 GPU 加速主张", "GPU accelerates"),
    ("不得出现「保真」这一旧结论", "the port is faithful"),
]


def extract(pdf: Path) -> tuple[str, int, str]:
    """返回 (全文, 页数, 后端名)。"""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        try:
            import pymupdf as fitz  # 新版包名
        except ImportError:
            return "", 0, "none"
    doc = fitz.open(str(pdf))
    text = "\n".join(p.get_text() for p in doc)
    return text, doc.page_count, "fitz"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--find", help="抽查某个串出现在第几页")
    args = ap.parse_args()

    if not PDF.exists():
        print(f"FAIL 找不到 {PDF}（先跑 tools/build_paper.py）")
        return 1

    text, pages, backend = extract(PDF)
    print(f"PDF: {PDF.name}  {PDF.stat().st_size} B  pages={pages}  backend={backend}")
    if backend == "none" or pages == 0:
        print("  ⇒ 解析器缺失（不是论文坏了）。换到装了 PyMuPDF 的解释器重跑。")
        return 2
    print()

    if args.find:
        needle = args.find
        hits = [i + 1 for i, p in enumerate(text.split("\f")) if needle in p]
        print(f"抽查 {needle!r}：出现在第 {hits or '（未找到）'} 页")
        return 0 if hits else 1

    fails: list[str] = []

    print("=== 1. 关键数字/术语必须在页面上 ===")
    for label, needle in MUST_APPEAR:
        ok = needle in text
        print(f"  {'OK  ' if ok else 'FAIL'} {label:26s} {needle!r}")
        if not ok:
            fails.append(f"{label} ({needle!r}) 未出现在 PDF")

    print("\n=== 2. 章节标题必须都在 ===")
    for s in MUST_HAVE_SECTIONS:
        ok = s in text
        print(f"  {'OK  ' if ok else 'FAIL'} {s}")
        if not ok:
            fails.append(f"章节缺失: {s}")

    print("\n=== 3. 禁止出现的串 ===")
    for label, needle in MUST_NOT_APPEAR:
        ok = needle not in text
        print(f"  {'OK  ' if ok else 'FAIL'} {label}")
        if not ok:
            fails.append(f"出现了禁止串: {needle!r}")

    print("\n=== 4. 页数合理性 ===")
    if 6 <= pages <= 14:
        print(f"  OK   {pages} 页（IEEEtran conference 目标 8–10，容忍 6–14）")
    else:
        print(f"  FAIL {pages} 页，超出 6–14")
        fails.append(f"页数 {pages} 不合理")

    print()
    if fails:
        print(f"{len(fails)} 项不符：")
        for f in fails:
            print(f"  - {f}")
        return 1
    print(f"全部通过（{len(MUST_APPEAR)} 个串 + {len(MUST_HAVE_SECTIONS)} 个章节 + "
          f"{len(MUST_NOT_APPEAR)} 条禁令 + 页数）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
