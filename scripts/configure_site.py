#!/usr/bin/env python3
"""Set the public Quartz base URL without exposing local vault paths."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[1]
CONFIG = SITE_ROOT / "quartz.config.yaml"
SAFE_PART = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")


def main() -> int:
    parser = argparse.ArgumentParser(description="配置 GitHub Pages 的 Quartz baseUrl")
    parser.add_argument("--github-user", required=True)
    parser.add_argument("--repository", default="personal-site")
    parser.add_argument("--custom-domain", help="可选；不含 https://")
    args = parser.parse_args()

    if not SAFE_PART.fullmatch(args.github_user) or not SAFE_PART.fullmatch(args.repository):
        parser.error("GitHub 用户名或仓库名包含不支持的字符")
    if args.custom_domain:
        base_url = args.custom_domain.removeprefix("https://").removeprefix("http://").strip("/")
        if "/" in base_url or "." not in base_url:
            parser.error("custom-domain 应是纯域名，不含协议或路径")
    else:
        base_url = f"{args.github_user}.github.io/{args.repository}"

    text = CONFIG.read_text(encoding="utf-8")
    updated, count = re.subn(
        r"^(\s*baseUrl:)\s*[^#\s]+",
        rf"\1 {base_url}",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise SystemExit("无法唯一定位 quartz.config.yaml 中的 baseUrl")
    CONFIG.write_text(updated, encoding="utf-8")

    print(f"baseUrl 已设置为：{base_url}")
    print(f"预期仓库：https://github.com/{args.github_user}/{args.repository}")
    print("脚本没有创建远端仓库或更改 Git remote。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
