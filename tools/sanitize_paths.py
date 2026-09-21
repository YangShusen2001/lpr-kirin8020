#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把本机特有前缀替换为占位符 —— 开源发布前的脱敏步骤。

## 设计原则

1. **只换前缀，不动路径结构。** `C:\\Users\\26671\\lpr-harmony\\LprDemo`
   → `<HOME>\\lpr-harmony\\LprDemo`。读者仍能看懂目录关系，本机用户名不再泄露。
2. **幂等。** 再跑一次不会二次替换（占位符不含被替换的模式）。
3. **可审计。** 默认 dry-run，打印每条规则命中多少次；`--apply` 才落盘。
4. **不改语义。** 不碰数字、不碰结论、不重写句子 —— 只做字面替换。

配套：`tools/scan_for_publication.py`（替换后重跑，确认 FAIL 归零）。

## 用法

    python tools/sanitize_paths.py                  # dry-run
    python tools/sanitize_paths.py --apply
    python tools/sanitize_paths.py --root <dir> --apply
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

# ---------------------------------------------------------------------------
# 规则在**运行时**从环境推导，不把本机用户名写进源码。
#
# 理由：本脚本本身也要进公开仓库。若把用户主目录的字面路径硬编码在规则里，
# 脚本自己就成了泄露源（第一版就是这样，被 scan_for_publication.py 抓出来了）。
# 现在换成 expanduser("~") —— 换一台机器照样能用，且源码里没有机器特有字符串。
# ---------------------------------------------------------------------------
HOME = os.path.expanduser("~").replace("\\", "/")
HOME_WIN = HOME.replace("/", "\\")


def _rules() -> list[tuple[str, str, str]]:
    H = re.escape(HOME)
    HW = re.escape(HOME_WIN)
    dev = r"D:[\\/]IDE[\\/]DevEco_Studio"
    return [
        # ---- 前期工程与语料（先于通用规则，避免被 <HOME> 吃掉）----
        (rf"{HW}[\\/]Desktop[\\/]Test[\\/]lpr-showcase", "<PRIOR_WORK>/lpr-showcase", "前期证据层"),
        (rf"{HW}[\\/]Desktop[\\/]ShusenPaper", "<PRIOR_WORK>/ShusenPaper", "前期表征工程"),
        (rf"{HW}[\\/]Desktop[\\/]HuaweiDocs", "<DOCS_CORPUS>", "本地文档语料"),
        (rf"{HW}[\\/]Desktop[\\/][^\\/\s]+", "<REPO>", "仓库根"),
        (rf"{H}[\\/]lpr-kirin8020-app", "<REPO>/lpr-kirin8020-app", "App 仓库"),
        (rf"{H}[\\/]lpr-harmony", "<PRIOR_WORK>/lpr-harmony", "前期 App 源码"),
        (rf"{H}[\\/]lpr-data", "<SCRATCH>/lpr-data", "临时数据目录"),
        (rf"{H}[\\/]om_probe2?", "<SCRATCH>/om_probe", "OMG 试验目录"),
        (rf"{H}[\\/]Desktop", "<HOME>/Desktop", "桌面"),
        # ---- 用户主目录（通用兜底，放最后）----
        (rf"{HW}", "<HOME>", "用户主目录"),
        (rf"{H}", "<HOME>", "用户主目录（WSL）"),
        # ---- 工具链 ----
        (rf"{dev}[\\/]sdk[\\/]default[\\/]openharmony", "<SDK>/openharmony", "SDK 根"),
        (rf"{dev}[\\/]sdk", "<SDK>", "SDK 根"),
        (rf"{dev}[\\/]jbr", "<JBR>", "DevEco 自带 JDK"),
        (rf"{dev}[\\/]tools[\\/]hvigor", "<HVIGOR>", "hvigor 构建器"),
        (rf"{dev}[\\/]tools[\\/]node", "<DEVECO_NODE>", "DevEco 自带 node"),
        (rf"{dev}", "<DEVECO_HOME>", "DevEco 安装根"),
        (r"D:[\\/]IDE[\\/]\.\.\.", "<SDK>/...", "省略写法的 SDK 路径"),
        (r"D:[\\/]IDE", "<DEVECO_HOME>", "DevEco 安装根（简写）"),
        (r"D:[\\/]Tools[\\/]mindspore-lite", "<MSLITE_DIR>", "MindSpore Lite 转换器"),
        (r"D:[\\/]Tools[\\/]NodeJS", "<NODE_HOME>", "系统 node"),
        (r"D:[\\/]Tools", "<TOOLS_DIR>", "工具目录"),
        # ---- 设备序列号 ----
        #
        # ⚠️ 这里**不能**用「16 位数字」这类宽松模式。第一版用了 `0000001\d{9}`，
        # 结果把华为文档页 ID `0000001053590180`（在 ddk-access-*.md 里是一条
        # 可核验的 URL）也替换掉了 —— **误伤事实性内容**。
        #
        # 真实设备序列号的形态是**大小写字母与数字混合**（本机实测 `4CY9K…`），
        # 而文档 ID 是纯数字。判据据此收紧：必须同时含大写字母和数字。
        (r"\b(?=[A-Z0-9]{14,20}\b)(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*\d)[A-Z0-9]{14,20}\b",
         "<DEVICE_SERIAL>", "设备序列号"),
    ]


RULES = _rules()

SKIP_DIRS = {".git", ".venv", "node_modules", "oh_modules", ".hvigor", "build",
             ".cxx", "__pycache__", ".pytest_cache", ".mypy_cache", "dist",
             ".mimosa", ".playwright-mcp"}
TEXT_EXT = {".md", ".txt", ".py", ".ts", ".ets", ".cpp", ".h", ".json", ".json5",
            ".sh", ".ps1", ".yaml", ".yml", ".tex", ".bib", ".csv", ".tsv",
            ".html", ".js", ".mjs", ".toml", ".cfg", ".xml"}


def published_files(root: str) -> list[str]:
    """返回**会被发布**的文件（相对路径）—— 与 scan_for_publication.py 同口径。

    用 git 的文件清单（已跟踪 + 未忽略的新文件），而不是遍历磁盘。
    遍历磁盘会把 `.gitignore` 里的东西（`_hw_docs/`、`_scratch/`、`.venv/`）
    也一起改写：既无意义，又会让「改了多少」这个数字失去参考价值。
    """
    import subprocess
    try:
        out = subprocess.run(
            ["git", "-C", root, "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True, text=True, timeout=60)
        if out.returncode == 0 and out.stdout.strip():
            return [p for p in out.stdout.splitlines() if p.strip()]
    except (OSError, subprocess.SubprocessError):
        pass
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            files.append(os.path.relpath(os.path.join(dirpath, fn), root).replace("\\", "/"))
    return files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--rules", action="store_true", help="只列规则")
    args = ap.parse_args()

    if args.rules:
        for pat, rep, note in RULES:
            print(f"{pat:70s} -> {rep:32s} ({note})")
        return 0

    compiled = [(re.compile(p), r, n) for p, r, n in RULES]
    root = os.path.abspath(args.root)
    print(f"{'APPLY' if args.apply else 'DRY-RUN'}  root = {root}\n")

    counts = {n: 0 for _, _, n in RULES}
    files_changed: set[str] = set()

    for rel in published_files(root):
        ext = os.path.splitext(rel)[1].lower()
        if ext not in TEXT_EXT and os.path.basename(rel) not in (".gitignore", "LICENSE"):
            continue
        full = os.path.join(root, rel)
        if not os.path.isfile(full):
            continue
        try:
            with io.open(full, encoding="utf-8", errors="strict") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        new = text
        hit_any = False
        for pat, rep, note in compiled:
            new, k = pat.subn(rep, new)
            if k:
                counts[note] += k
                hit_any = True
        if hit_any and new != text:
            files_changed.add(rel)
            if args.apply:
                with io.open(full, "w", encoding="utf-8", newline="") as f:
                    f.write(new)

    print("规则命中统计：")
    for _, _, note in RULES:
        if counts[note]:
            print(f"  {note:28s} {counts[note]:4d}")
    total = sum(counts.values())
    print(f"\n合计 {total} 处，涉及 {len(files_changed)} 个文件。")
    for rel in sorted(files_changed)[:40]:
        print(f"  {rel}")
    if len(files_changed) > 40:
        print(f"  … 另有 {len(files_changed) - 40} 个")

    if not args.apply and total:
        print("\n（dry-run，未落盘。加 --apply 执行。）")
    elif args.apply:
        print("\n已落盘。请重跑 tools/scan_for_publication.py 复核。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
