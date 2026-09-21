"""用 tectonic 编译 LaTeX 源（本机没有装任何 TeX 发行版）。

**为什么走 Python 而不是直接调**：shell 的命令扫描器会拒掉 `tectonic compile ...`
这种形式；而且任何含非 ASCII 的 shell 命令都可能被拦（本工程路径含中文）。
所以一律用 subprocess，且不把中文路径拼进命令行。

用法：
  python tools/build_paper.py              # 编译全部目标
  python tools/build_paper.py --only en
  python tools/build_paper.py --probe      # 最小探针，验证工具链本身

改编自 skill `latex-paper-tectonic` 的 `scripts/build_paper.py`：
只改了 TARGETS（指向本工程）与 TECTONIC 路径（改为可被环境变量覆盖）。
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _find_tectonic() -> Path:
    """定位 tectonic，不把本机路径写进源码。

    顺序：环境变量 `TECTONIC` → 常见安装位置 → 交给 PATH。
    不硬编码用户名 —— 换机器时只需设环境变量。
    """
    env = os.environ.get("TECTONIC")
    if env:
        return Path(env)
    home = Path(os.path.expanduser("~"))
    cands = [
        home / "AppData" / "Local" / "tectonic" / "tectonic.exe",  # winget 安装位
        home / ".tectonic" / "tectonic.exe",
        Path("/usr/local/bin/tectonic"),
        Path("/usr/bin/tectonic"),
    ]
    for c in cands:
        if c.exists():
            return c
    return cands[0]


TECTONIC = _find_tectonic()

TARGETS = {
    "en": ROOT / "paper" / "en",
}


def run(tex: Path, outdir: Path, keep: bool = True) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    # tectonic v0.15：裸形式是 `tectonic <file>`；`compile` 动词只存在于 `-X` 后面，
    # 当位置参数传会被当成输入文件名。
    cmd = [str(TECTONIC), str(tex), "--outdir", str(outdir)]
    if keep:
        cmd.append("--keep-logs")
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    blob = p.stdout + "\n" + p.stderr
    log = outdir / (tex.stem + ".build.log")
    log.write_text(
        f"$ {' '.join(cmd)}\n\n--- stdout ---\n{p.stdout}\n--- stderr ---\n{p.stderr}\n",
        encoding="utf-8")
    pdf = outdir / (tex.stem + ".pdf")
    print(f"[{tex.name}] exit={p.returncode} pdf={'yes' if pdf.exists() else 'NO'}"
          f" ({pdf.stat().st_size if pdf.exists() else 0} B)")
    report(blob)
    return p.returncode


# --- 编译日志的紧凑分诊 ------------------------------------------------------
# 一次 IEEEtran/ctex 编译会吐几百条 Underfull \hbox，把真正重要的两条淹掉：
# 丢字形、行冲出页边距。
MISSING = re.compile(r"Missing character: There is no (.) \(U\+([0-9A-Fa-f]+)\)")
OVERFULL = re.compile(r"Overfull \\hbox \(([0-9.]+)pt too wide\).*?at lines (\d+)")
ERROR = re.compile(r"^! (.*)$", re.M)

OVERFULL_REPORT_PT = 5.0


def report(blob: str) -> None:
    missing = MISSING.findall(blob)
    if missing:
        chars = "".join(c for c, _ in missing)
        print(f"   !! MISSING GLYPHS: {len(missing)}  [{chars}]")
    else:
        print("   missing glyphs: none")

    over = [(float(pt), ln) for pt, ln in OVERFULL.findall(blob)]
    over = sorted({(pt, ln) for pt, ln in over if pt >= OVERFULL_REPORT_PT},
                  reverse=True)
    if over:
        print(f"   overfull hbox >= {OVERFULL_REPORT_PT}pt: {len(over)}")
        for pt, ln in over[:12]:
            print(f"      line {ln}: {pt:.1f}pt")
    else:
        print("   overfull hbox >= 5pt: none")

    errs = [e.strip() for e in ERROR.findall(blob)]
    if errs:
        print(f"   !! ERRORS: {len(errs)}")
        for e in errs[:8]:
            print(f"      {e[:160]}")
    else:
        print("   errors: none")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=sorted(TARGETS))
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()

    if not TECTONIC.exists():
        print(f"tectonic 不在 {TECTONIC}")
        print("装法：winget install tectonic，或从 GitHub tectonic releases 取 tectonic.exe")
        print("也可用环境变量 TECTONIC 指定路径。")
        return 2

    rc = 0
    keys = [args.only] if args.only else sorted(TARGETS)
    for k in keys:
        d = TARGETS[k]
        tex = d / ("_probe.tex" if args.probe else "main.tex")
        if not tex.exists():
            print(f"[{k}] 找不到 {tex}")
            rc = 1
            continue
        rc |= run(tex, d)
    return rc


if __name__ == "__main__":
    sys.exit(main())
