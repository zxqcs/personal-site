#!/usr/bin/env python3
"""Create a non-history-rewriting rollback commit for published content."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from security_scan import format_findings, scan_tree

SITE_ROOT = Path(__file__).resolve().parents[1]
PATHS = ["content", "config/published-manifest.json"]


class RollbackError(RuntimeError):
    pass


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=SITE_ROOT, text=True, capture_output=capture, check=False)
    if result.returncode != 0:
        raise RollbackError(result.stderr.strip() or f"命令失败：{' '.join(command)}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="把线上发布副本恢复到已知正常提交")
    parser.add_argument("--to", required=True, metavar="COMMIT")
    parser.add_argument("--apply", action="store_true", help="确认后创建回滚提交")
    parser.add_argument("--push", action="store_true", help="再次确认后 push")
    args = parser.parse_args()

    try:
        if run(["git", "status", "--porcelain"], capture=True).stdout.strip():
            raise RollbackError("工作区必须完全干净，避免覆盖未提交内容")
        target = run(["git", "rev-parse", "--verify", f"{args.to}^{{commit}}"], capture=True).stdout.strip()
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", target, "HEAD"],
            cwd=SITE_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if ancestor.returncode != 0:
            raise RollbackError("目标必须是当前分支的祖先提交")
        run(["git", "cat-file", "-e", f"{target}:config/published-manifest.json"])
        run(["git", "cat-file", "-e", f"{target}:content/.publish-managed"])
        diff = run(["git", "diff", "--stat", target, "HEAD", "--", *PATHS], capture=True).stdout
        print(f"回滚目标：{target}\n")
        print(diff or "发布内容与目标没有差异。")
        if not args.apply:
            print("dry-run 完成；添加 --apply 才会创建回滚提交。")
            return 0
        if input("仅将网站发布副本恢复到该提交？PublicVault 不会改变。[y/N] ").strip().lower() != "y":
            print("已取消。")
            return 3

        run(["git", "restore", "--source", target, "--", *PATHS])
        findings = scan_tree(SITE_ROOT / "content")
        if findings:
            run(["git", "restore", "--source", "HEAD", "--", *PATHS])
            raise RollbackError(format_findings(findings))
        run(["git", "add", "--", *PATHS])
        run(["git", "commit", "-m", f"rollback: restore published content to {target[:12]}"])
        print("已创建新的回滚提交；Git 历史没有被改写。")

        if args.push:
            remote = run(["git", "remote", "get-url", "origin"], capture=True).stdout.strip()
            print(f"即将推送到：{remote}")
            if input("继续 push 并触发 Pages？[y/N] ").strip().lower() != "y":
                print("已保留本地回滚提交，未 push。")
                return 3
            run(["git", "push", "origin", "main"])
        return 0
    except (OSError, RollbackError) as exc:
        print(f"回滚已阻断：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
