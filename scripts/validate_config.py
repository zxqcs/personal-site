#!/usr/bin/env python3
"""Validate deployment configuration and privacy-critical repository invariants."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[1]
CONFIG = SITE_ROOT / "quartz.config.yaml"
MANIFEST = SITE_ROOT / "config" / "published-manifest.json"
LOCAL_CONFIG = "config/publish.local.toml"


def main() -> int:
    errors: list[str] = []
    text = CONFIG.read_text(encoding="utf-8")
    match = re.search(r"^\s*baseUrl:\s*([^#\s]+)", text, re.MULTILINE)
    if not match:
        errors.append("quartz.config.yaml 缺少 baseUrl")
    elif "YOUR_GITHUB_USERNAME" in match.group(1):
        errors.append("baseUrl 仍含占位符；先运行 scripts/configure_site.py")
    elif match.group(1).startswith(("http://", "https://")):
        errors.append("baseUrl 不应包含协议前缀")

    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if manifest.get("schema") != 1 or not isinstance(manifest.get("files"), dict):
            errors.append("published-manifest.json 格式无效")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"无法读取 published-manifest.json：{exc}")

    marker = SITE_ROOT / "content" / ".publish-managed"
    if not marker.is_file() or marker.is_symlink():
        errors.append("content 缺少普通文件形式的 .publish-managed 标记")

    for path in (SITE_ROOT / "content").rglob("*"):
        if path.is_symlink():
            errors.append(f"content 含符号链接：{path.relative_to(SITE_ROOT)}")

    if (SITE_ROOT / ".git").exists():
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", LOCAL_CONFIG],
            cwd=SITE_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if tracked.returncode == 0:
            errors.append(f"本机路径配置被 Git 跟踪：{LOCAL_CONFIG}")

    workflow = (SITE_ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
    for expected in (
        "actions/checkout@v7",
        "actions/setup-node@v7",
        "actions/upload-pages-artifact@v5",
        "actions/deploy-pages@v5",
    ):
        if expected not in workflow:
            errors.append(f"Pages workflow 缺少预期官方 action：{expected}")

    if errors:
        print("配置验证失败：", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print("配置验证通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
