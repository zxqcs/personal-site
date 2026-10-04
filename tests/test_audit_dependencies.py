from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_dependencies as audit  # noqa: E402


def reviewed_case() -> tuple[dict, dict]:
    report = {
        "vulnerabilities": {
            name: {
                "severity": "high",
                "via": ([{"url": value[0]}] if name == "braces" else value),
            }
            for name, (_, value) in audit.REVIEWED_CHAIN.items()
        }
    }
    lock = {
        "packages": {
            f"node_modules/{name}": {"version": version}
            for name, (version, _) in audit.REVIEWED_CHAIN.items()
        }
    }
    return report, lock


class AuditPolicyTests(unittest.TestCase):
    def test_exact_reviewed_chain_is_allowed(self) -> None:
        report, lock = reviewed_case()
        self.assertTrue(audit.check_report(report, lock))

    def test_unrelated_high_advisory_fails(self) -> None:
        report, lock = reviewed_case()
        report["vulnerabilities"]["other-package"] = {"severity": "high", "via": []}
        with self.assertRaises(audit.AuditError):
            audit.check_report(report, lock)

    def test_new_advisory_on_reviewed_package_fails(self) -> None:
        report, lock = reviewed_case()
        report["vulnerabilities"]["braces"]["via"].append({"url": "https://example.test/new"})
        with self.assertRaises(audit.AuditError):
            audit.check_report(report, lock)

    def test_dependency_update_requires_review(self) -> None:
        report, lock = reviewed_case()
        lock["packages"]["node_modules/braces"]["version"] = "3.0.4"
        with self.assertRaises(audit.AuditError):
            audit.check_report(report, lock)

    def test_no_high_advisories_passes(self) -> None:
        report, lock = reviewed_case()
        report["vulnerabilities"] = {}
        self.assertFalse(audit.check_report(report, lock))


if __name__ == "__main__":
    unittest.main()
