#!/usr/bin/env python3
"""Build, review, commit, and optionally push only publisher-managed content."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from security_scan import format_findings, scan_tree

SITE_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_PREFIXES = ("content/",)
ALLOWED_FILES = {"config/published-manifest.json"}


class ReleaseError(RuntimeError):
    pass


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=SITE_ROOT,
        text=True,
        capture_output=capture,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() if capture else ""
        raise ReleaseError(f"命令失败：{' '.join(command)} {detail}")
    return result


def changed_paths() -> list[str]:
    result = run(["git", "status", "--porcelain=v1", "-z"], capture=True)
    paths: list[str] = []
    records = result.stdout.split("\0")
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        status, path = record[:2], record[3:]
        if "R" in status or "C" in status:
            if index >= len(records):
                raise ReleaseError("无法解析 Git rename 状态")
            path = records[index]
            index += 1
        paths.append(path)
    return sorted(set(paths))


def is_allowed(path: str) -> bool:
    return path in ALLOWED_FILES or path.startswith(ALLOWED_PREFIXES)


def require_safe_remote() -> str:
    result = run(["git", "remote", "get-url", "origin"], capture=True)
    remote = result.stdout.strip()
    if "jackyzha0/quartz" in remote or not remote:
        raise ReleaseError("origin 未配置为你自己的 GitHub 网站仓库")
    return remote


def require_node_24() -> None:
    result = run(["node", "--version"], capture=True)
    version = result.stdout.strip()
    if not version.startswith("v24."):
        raise ReleaseError(
            f"本项目要求 Node.js 24，当前为 {version or '未知版本'}；"
            "请按照 .node-version 切换后重试"
        )


def quality_gate() -> None:
    require_node_24()
    findings = scan_tree(SITE_ROOT / "content")
    if findings:
        raise ReleaseError(format_findings(findings))
    run([sys.executable, "scripts/validate_config.py"])
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    run(["npm", "audit", "--audit-level=high"])
    run(["npm", "run", "test:image"])
    run(["npm", "run", "check"])
    run(["npx", "quartz", "build"])
    findings = scan_tree(SITE_ROOT / "public")
    if findings:
        raise ReleaseError(format_findings(findings))


def main() -> int:
    parser = argparse.ArgumentParser(description="审核、构建并发布已管理的公开内容")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--release", action="store_true")
    parser.add_argument("--push", action="store_true", help="commit 后再确认并 push origin main")
    parser.add_argument("--message", default="publish: update public content")
    args = parser.parse_args()

    try:
        run(["git", "rev-parse", "--is-inside-work-tree"], capture=True)
        branch = run(["git", "branch", "--show-current"], capture=True).stdout.strip()
        if branch != "main":
            raise ReleaseError(f"只允许从 main 发布，当前分支为 {branch or '(detached)'}")
        paths = changed_paths()
        if not paths:
            print("没有待发布的本地变化。")
            return 0
        unexpected = [path for path in paths if not is_allowed(path)]
        if unexpected:
            raise ReleaseError("存在非发布工具管理的变化：" + ", ".join(unexpected))

        print("待提交文件：")
        for path in paths:
            print(f"  {path}")
        quality_gate()
        print("\n质量门通过；本地构建产物未提交。")
        if args.dry_run:
            print("release dry-run 完成：未 commit、未 push。")
            return 0

        remote = require_safe_remote()
        if input("创建本地公开发布提交？[y/N] ").strip().lower() != "y":
            print("已取消；未 commit。")
            return 3
        run(["git", "add", "--", "content", "config/published-manifest.json"])
        staged = run(["git", "diff", "--cached", "--name-only", "-z"], capture=True).stdout
        staged_paths = [path for path in staged.split("\0") if path]
        if any(not is_allowed(path) for path in staged_paths):
            raise ReleaseError("暂存区出现非管理文件，拒绝 commit")
        run(["git", "commit", "-m", args.message])
        print("本地发布提交已创建。")

        if args.push:
            print(f"即将把 main 推送到：{remote}")
            if input("这会进入公开 Git 历史并触发 Pages。继续？[y/N] ").strip().lower() != "y":
                print("已保留本地 commit，未 push。")
                return 3
            run(["git", "push", "origin", "main"])
            print("已 push；GitHub Actions 将执行部署。")
        return 0
    except (OSError, ReleaseError) as exc:
        print(f"release 已阻断：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
