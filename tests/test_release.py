from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import release  # noqa: E402


class ReleaseRuntimeTests(unittest.TestCase):
    def test_node_24_is_accepted(self) -> None:
        completed = subprocess.CompletedProcess(["node", "--version"], 0, "v24.21.0\n", "")
        with mock.patch.object(release, "run", return_value=completed):
            release.require_node_24()

    def test_other_node_major_is_rejected(self) -> None:
        completed = subprocess.CompletedProcess(["node", "--version"], 0, "v25.2.1\n", "")
        with mock.patch.object(release, "run", return_value=completed):
            with self.assertRaisesRegex(release.ReleaseError, "Node.js 24"):
                release.require_node_24()


if __name__ == "__main__":
    unittest.main()
