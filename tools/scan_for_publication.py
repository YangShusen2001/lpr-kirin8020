#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开源发布前的合规扫描。

## 为什么需要它

把仓库从 private 转 public 是**不可逆**的（fork 与缓存会留存）。
发布前要清掉的东西分散在三类文件里，靠人眼扫一定会漏：

1. **本机路径** —— 泄露目录结构，也让复现者无法照抄（应为占位符）。
2. **设备标识 / 账号** —— 设备序列号、邮箱、token。
3. **不可再分发的资产** —— 厂商 DDK、数据集、工单材料。

## 用法

    python tools/scan_for_publication.py                  # 扫当前仓库
    python tools/scan_for_publication.py --root <dir>
    python tools/scan_for_publication.py --only-paths     # 只扫绝对路径

退出码 0 = 无阻断项；1 = 有 FAIL（**不得转 public**）。
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

# (类别, 正则, 严重度, 说明)
PATTERNS = [
    ("本机路径", re.compile(r"[A-Za-z]:[\\/](?:Users|IDE|Tools|Applications)[\\/][^\s`'\"）)]*"),
     "FAIL", "绝对路径：应为占位符或相对路径"),
    ("本机路径", re.compile(r"(?<![A-Za-z]:)(?<![A-Za-z])(?:~/|/Users/|/home/)[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+"),
     "WARN", "POSIX 绝对路径：确认是否为通用写法（如 ~/.workbuddy 可接受）"),
    # 设备序列号：**必须同时含大写字母与数字**。
    #
    # 第一版用 `\b0000001\d{9}\b`（16 位数字），把华为文档页 ID
    # `0000001053590180`（`ddk-access-*.md` 里一条可核验的 URL）误报成序列号，
    # 连带让 sanitize_paths.py 把它替换掉了 —— 误伤事实性内容。
    # 本机实测的序列号形态是 `4CY9K…`：大小写字母 + 数字。判据据此收紧。
    ("设备标识", re.compile(r"\b(?=[A-Z0-9]{14,20}\b)(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*\d)[A-Z0-9]{14,20}\b"),
     "FAIL", "疑似设备序列号（字母数字混合；纯数字不算，那是文档 ID）"),
    ("账号", re.compile(r"[A-Za-z0-9._%+-]+@(?:qq|gmail|163|outlook|hotmail)\.[A-Za-z]{2,}"),
     "WARN", "邮箱：确认是否为有意公开的联系方式"),
    ("凭据", re.compile(r"\b(?:gh[oprsu]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b"),
     "FAIL", "疑似 token / API key"),
    ("工单材料", re.compile(r"(?:工单号|受理编号|服务单号|case\s*id)\s*[:：]?\s*[A-Za-z0-9-]{6,}"),
     "WARN", "厂商工单标识：发布前须脱敏"),
]

# 不可再分发的**目录**（被跟踪即阻断）
FORBIDDEN_DIRS = [
    ("ddk", "厂商 DDK：不可再分发，只留获取步骤"),
    (".venv", "虚拟环境：可由依赖重建"),
    ("node_modules", "依赖目录：可由 lockfile 重建"),
    ("oh_modules", "HarmonyOS 依赖目录"),
    (".hvigor", "构建缓存"),
    ("build", "构建产物"),
]

# 不可再分发的**文件扩展名**（被跟踪即阻断）
#
# 注意：只按目录名判会把 `models_om/logs/*.txt`（OMG 的转换日志，是证据）误报成产物。
# 真正的边界是**二进制产物**，所以这里按扩展名判。
FORBIDDEN_EXT = {
    ".om": "CANN 产物",
    ".omc": "CANN 产物",
    ".ms": "MindSpore Lite 产物",
    ".onnx": "模型权重",
    ".ncnn.bin": "ncnn 权重",
    ".p12": "签名材料",
    ".cer": "签名材料",
    ".p7b": "签名材料",
    ".hap": "打包产物",
}

# 需要**人工确认许可**的扩展名（不阻断，但发布前必须逐个决定）
CAUTION_EXT = {
    ".so": "预编译动态库：确认上游许可是否允许再分发，否则改为文档化获取步骤",
    ".a": "预编译静态库：同上",
    ".ncnn.param": "ncnn 网络结构文件：确认上游许可",
}

SKIP_DIRS = {".git", ".venv", "node_modules", "oh_modules", ".hvigor", "build",
             ".cxx", "__pycache__", ".pytest_cache", ".mypy_cache", "dist"}
TEXT_EXT = {".md", ".txt", ".py", ".ts", ".ets", ".cpp", ".h", ".json", ".json5",
            ".sh", ".ps1", ".yaml", ".yml", ".tex", ".bib", ".csv", ".tsv",
            ".html", ".js", ".mjs", ".gitignore", ".toml", ".cfg", ".xml"}


def published_files(root: str) -> list[str]:
    """返回**会被发布**的文件（相对路径）。

    关键：扫描范围必须是 git 实际跟踪的文件，而不是磁盘上的一切。
    否则 `.gitignore` 里的临时产物（`.mimosa/`、`_scratch/`、`.playwright-mcp/`）
    会被当成泄露报出来 —— 它们根本不会进仓库，属噪声。
    """
    import subprocess
    try:
        # --cached：已跟踪；--others --exclude-standard：**新增但未被忽略**的文件。
        # 只用 ls-files（默认 = --cached）会漏掉刚写好、还没 commit 的文件 ——
        # 而那恰恰是最容易带进本机路径的东西。
        out = subprocess.run(
            ["git", "-C", root, "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True, text=True, timeout=60)
        if out.returncode == 0 and out.stdout.strip():
            return [p for p in out.stdout.splitlines() if p.strip()]
    except (OSError, subprocess.SubprocessError):
        pass
    # 回退：非 git 目录，遍历磁盘
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            files.append(os.path.relpath(os.path.join(dirpath, fn), root).replace("\\", "/"))
    return files


def scan_text(root: str) -> list[tuple[str, str, int, str, str]]:
    hits: list[tuple[str, str, int, str, str]] = []
    for rel in published_files(root):
        ext = os.path.splitext(rel)[1].lower()
        if ext not in TEXT_EXT and os.path.basename(rel) not in (".gitignore", "LICENSE"):
            continue
        full = os.path.join(root, rel)
        if not os.path.isfile(full):
            continue
        try:
            with io.open(full, encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    for kind, pat, sev, note in PATTERNS:
                        for m in pat.finditer(line):
                            s = m.group(0)
                            if s.startswith("~/") or s.startswith("/tmp"):
                                continue
                            hits.append((sev, kind, i, rel, f"{s}  ← {note}"))
        except OSError:
            continue
    return hits


def scan_assets(root: str) -> tuple[list[str], list[str]]:
    """检查**被跟踪的**不可再分发资产。

    返回 (阻断, 需确认)。分两档的理由：`.om`/`.ms`/`.onnx` 是明确的不可再分发；
    而 `.so`/`.ncnn.param` 是第三方许可问题，需要人逐个判断，不该由脚本替他决定。
    """
    blocking, caution = set(), set()
    for rel in published_files(root):
        parts = rel.replace("\\", "/").split("/")
        for part in parts[:-1]:
            for frag, note in FORBIDDEN_DIRS:
                if part == frag:
                    blocking.add(f"{'/'.join(parts[:parts.index(part) + 1])}/  ← {note}")
        low = rel.lower()
        for ext, note in FORBIDDEN_EXT.items():
            if low.endswith(ext):
                blocking.add(f"{rel}  ← {note}（被跟踪）")
        for ext, note in CAUTION_EXT.items():
            if low.endswith(ext):
                caution.add(f"{rel}  ← {note}")
    return sorted(blocking), sorted(caution)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--only-paths", action="store_true")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    print(f"扫描根目录: {root}\n")

    hits = scan_text(root)
    fails = [h for h in hits if h[0] == "FAIL"]
    warns = [h for h in hits if h[0] == "WARN"]

    def show(title: str, items, key) -> None:
        print(f"=== {title}（{len(items)}）===")
        if not items:
            print("  （无）\n")
            return
        for h in items[:60]:
            print(f"  {h[3]}:{h[2]}  [{h[1]}] {h[4]}")
        if len(items) > 60:
            print(f"  … 另有 {len(items) - 60} 条")
        print()

    show("FAIL · 阻断项", fails, None)
    show("WARN · 需确认", warns, None)

    if not args.only_paths:
        blocking, caution = scan_assets(root)
        print(f"=== 不可再分发的资产（阻断，{len(blocking)}）===")
        print("  （无）" if not blocking else "")
        for a in blocking:
            print(f"  {a}")
        print()
        print(f"=== 需人工确认许可的资产（{len(caution)}）===")
        print("  （无）" if not caution else "")
        for a in caution[:30]:
            print(f"  {a}")
        if len(caution) > 30:
            print(f"  … 另有 {len(caution) - 30} 个")
        print()
    else:
        blocking = []

    if fails or blocking:
        print(f"结论：{len(fails)} 项文本阻断 + {len(blocking)} 项资产阻断 "
              f"—— **不得转 public**，先清理。")
        return 1
    print(f"结论：无阻断项（{len(warns)} 项文本待确认）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
