#!/usr/bin/env python3
"""Fail-closed, value-redacting secret and symlink scan for publishable trees."""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

MAX_FILE_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class Finding:
    path: str
    line: int | None
    rule: str


SECRET_RULES = (
    ("private-key", re.compile(r"-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----")),
    ("github-token", re.compile(r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{20,}\b")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("bearer-token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE)),
    (
        "credential-assignment",
        re.compile(
            r"\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|password)"
            r"\s*[:=]\s*[\"']?[^\s\"'`]{8,}",
            re.IGNORECASE,
        ),
    ),
)

SENSITIVE_NAMES = {
    ".env",
    ".env.local",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "secrets.json",
}


class ScanError(RuntimeError):
    pass


def scan_tree(root: Path) -> list[Finding]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ScanError(f"不是目录：{root}")

    findings: list[Finding] = []
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in tuple(dirs) + tuple(files):
            path = current_path / name
            if path.is_symlink():
                findings.append(Finding(path.relative_to(root).as_posix(), None, "symbolic-link"))

        for name in files:
            path = current_path / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                continue
            if name.lower() in SENSITIVE_NAMES or name.lower().startswith(".env."):
                findings.append(Finding(rel, None, "sensitive-filename"))
                continue
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                findings.append(Finding(rel, None, "file-too-large-to-scan"))
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            except OSError as exc:
                raise ScanError(f"无法读取 {rel}: {exc}") from exc
            for line_no, line in enumerate(text.splitlines(), 1):
                for rule, pattern in SECRET_RULES:
                    if pattern.search(line):
                        findings.append(Finding(rel, line_no, rule))
    return findings


def format_findings(findings: list[Finding]) -> str:
    lines = ["安全扫描阻断：发现以下可疑项（不会显示疑似秘密的值）："]
    for finding in findings:
        where = f"{finding.path}:{finding.line}" if finding.line else finding.path
        lines.append(f"  - {where} [{finding.rule}]")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="扫描即将公开的目录，不输出秘密原文")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    all_findings: list[Finding] = []
    for path in args.paths:
        try:
            findings = scan_tree(path)
        except (OSError, ScanError) as exc:
            print(f"安全扫描失败：{exc}", file=sys.stderr)
            return 2
        all_findings.extend(
            Finding(f"{path}/{item.path}", item.line, item.rule) for item in findings
        )

    if all_findings:
        print(format_findings(all_findings), file=sys.stderr)
        return 1
    print("安全扫描通过：未发现已知的秘密模式、敏感文件名或符号链接。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
