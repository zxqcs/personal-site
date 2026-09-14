from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import publish  # noqa: E402


class PublishTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp())
        self.source = self.temp / "PublicVault"
        self.site = self.temp / "personal-site"
        self.content = self.site / "content"
        self.config_dir = self.site / "config"
        self.source.mkdir()
        self.content.mkdir(parents=True)
        self.config_dir.mkdir()
        (self.content / publish.MARKER).write_text("managed\n", encoding="utf-8")
        (self.source / "index.md").write_text("# Home\n", encoding="utf-8")
        (self.source / "thoughts").mkdir()
        self.local_config = self.config_dir / "publish.local.toml"
        self.local_config.write_text(f'public_vault = "{self.source}"\n', encoding="utf-8")
        self.manifest = self.config_dir / "published-manifest.json"
        self.manifest.write_text(
            json.dumps({"schema": 1, "tree_digest": "", "files": {}}), encoding="utf-8"
        )
        self.patch = mock.patch.multiple(
            publish,
            SITE_ROOT=self.site,
            CONTENT_ROOT=self.content,
            CONFIG_PATH=self.local_config,
            MANIFEST_PATH=self.manifest,
        )
        self.patch.start()

    def tearDown(self) -> None:
        self.patch.stop()
        shutil.rmtree(self.temp)

    def publish(self) -> int:
        with mock.patch("builtins.input", return_value="y"):
            return publish.run("publish")

    def test_dry_run_does_not_change_content(self) -> None:
        before = list(self.content.iterdir())
        self.assertEqual(publish.run("dry-run"), 0)
        self.assertEqual(before, list(self.content.iterdir()))
        self.assertFalse((self.content / "index.md").exists())

    def test_publish_copies_only_public_vault(self) -> None:
        private = self.temp / "PrivateVault"
        private.mkdir()
        (private / "PRIVATE_SENTINEL.txt").write_text("never publish", encoding="utf-8")
        (self.source / "thoughts" / "hello.md").write_text("# Hello\n", encoding="utf-8")
        self.assertEqual(self.publish(), 0)
        self.assertTrue((self.content / "thoughts" / "hello.md").is_file())
        self.assertFalse(any("PRIVATE_SENTINEL" in str(path) for path in self.content.rglob("*")))

    def test_secret_blocks_publish(self) -> None:
        (self.source / "thoughts" / "bad.md").write_text(
            "token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ12\n", encoding="utf-8"
        )
        with self.assertRaises(publish.PublishError):
            publish.run("dry-run")
        self.assertFalse((self.content / "thoughts" / "bad.md").exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink unsupported")
    def test_symlink_blocks_publish(self) -> None:
        outside = self.temp / "outside.md"
        outside.write_text("private", encoding="utf-8")
        os.symlink(outside, self.source / "thoughts" / "escape.md")
        with self.assertRaises(publish.PublishError):
            publish.run("dry-run")

    def test_direct_edit_of_content_blocks_next_publish(self) -> None:
        self.assertEqual(self.publish(), 0)
        (self.content / "index.md").write_text("direct edit", encoding="utf-8")
        with self.assertRaises(publish.PublishError):
            publish.run("dry-run")

    def test_confirmation_invalidated_when_source_changes(self) -> None:
        def change_source(_: str) -> str:
            (self.source / "index.md").write_text("# Changed after preview\n", encoding="utf-8")
            return "y"

        with mock.patch("builtins.input", side_effect=change_source):
            with self.assertRaises(publish.PublishError):
                publish.run("publish")
        self.assertFalse((self.content / "index.md").exists())

    def test_deletion_removes_previously_managed_file(self) -> None:
        article = self.source / "thoughts" / "temporary.md"
        article.write_text("# Temporary\n", encoding="utf-8")
        self.assertEqual(self.publish(), 0)
        article.unlink()
        self.assertEqual(self.publish(), 0)
        self.assertFalse((self.content / "thoughts" / "temporary.md").exists())

    def test_parent_reference_is_blocked(self) -> None:
        (self.source / "thoughts" / "bad-link.md").write_text(
            "![outside](../private.png)\n", encoding="utf-8"
        )
        with self.assertRaises(publish.PublishError):
            publish.run("dry-run")


if __name__ == "__main__":
    unittest.main()
