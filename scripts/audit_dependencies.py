#!/usr/bin/env python3
"""Fail on high-severity npm advisories except one reviewed build-only chain."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[1]
ADVISORY = "https://github.com/advisories/GHSA-vfj7-8cjw-p6xm"

# Quartz invokes globby with patterns from this repository during build/watch.
# The published site is static and does not run these packages for visitors.
# GHSA-vfj7-8cjw-p6xm currently has no patched braces release. Review this
# exception whenever these locked versions or the call sites change.
REVIEWED_CHAIN = {
    "braces": ("3.0.3", [ADVISORY]),
    "micromatch": ("4.0.8", ["braces"]),
    "fast-glob": ("3.3.3", ["micromatch"]),
    "globby": ("16.2.4", ["fast-glob", "micromatch"]),
}


class AuditError(RuntimeError):
    pass


def check_report(report: dict, lock: dict) -> bool:
    if "error" in report or not isinstance(report.get("vulnerabilities"), dict):
        raise AuditError("npm audit 未返回有效的漏洞报告")

    high = {
        name: item
        for name, item in report["vulnerabilities"].items()
        if item.get("severity") in {"high", "critical"}
    }
    if not high:
        return False
    if set(high) != set(REVIEWED_CHAIN):
        raise AuditError("发现未评估的高危或严重依赖：" + ", ".join(sorted(high)))

    packages = lock.get("packages", {})
    for name, (version, expected_via) in REVIEWED_CHAIN.items():
        item = high[name]
        if item.get("severity") != "high":
            raise AuditError(f"{name} 的严重级别已变化，需重新评估")
        actual_version = packages.get(f"node_modules/{name}", {}).get("version")
        if actual_version != version:
            raise AuditError(f"{name} 锁定版本已变化，需重新评估")
        via = item.get("via")
        if not isinstance(via, list):
            raise AuditError(f"{name} 的审计链路无效")
        actual_via: list[str] = []
        for entry in via:
            value = entry.get("url") if isinstance(entry, dict) else entry
            if not isinstance(value, str):
                raise AuditError(f"{name} 的审计链路无效")
            actual_via.append(value)
        if sorted(actual_via) != sorted(expected_via):
            raise AuditError(f"{name} 出现新的告警或依赖链路，需重新评估")
    return True


def main() -> int:
    try:
        result = subprocess.run(
            ["npm", "audit", "--json"], cwd=SITE_ROOT, text=True, capture_output=True, check=False
        )
        if result.returncode not in {0, 1}:
            raise AuditError(result.stderr.strip() or "npm audit 执行失败")
        report = json.loads(result.stdout)
        lock = json.loads((SITE_ROOT / "package-lock.json").read_text(encoding="utf-8"))
        reviewed = check_report(report, lock)
    except (OSError, json.JSONDecodeError, AuditError) as exc:
        print(f"依赖审计未通过：{exc}", file=sys.stderr)
        return 1

    if reviewed:
        print(f"依赖审计通过；已评估的构建依赖例外：{ADVISORY}")
    else:
        print("依赖审计通过：无高危或严重告警。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
