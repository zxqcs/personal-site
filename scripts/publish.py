#!/usr/bin/env python3
"""Safely mirror PublicVault into Quartz content after review and confirmation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import tomllib
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from security_scan import format_findings, scan_tree

SITE_ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = SITE_ROOT / "content"
CONFIG_PATH = SITE_ROOT / "config" / "publish.local.toml"
MANIFEST_PATH = SITE_ROOT / "config" / "published-manifest.json"
MARKER = ".publish-managed"

ALLOWED_TOP_FILES = {"index.md"}
ALLOWED_TOP_DIRS = {"about", "thoughts", "essays", "projects", "fiction", "assets"}
ALLOWED_SUFFIXES = {
    ".md",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".avif",
    ".svg",
    ".pdf",
}
IGNORED_ROOT_NAMES = {".git", ".obsidian", ".DS_Store", "Thumbs.db"}
INLINE_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
WIKILINK_RE = re.compile(r"!?\[\[([^\]|#]+)")


class PublishError(RuntimeError):
    pass


@dataclass(frozen=True)
class Snapshot:
    files: dict[str, str]
    tree_digest: str


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_snapshot(files: dict[str, str]) -> Snapshot:
    digest = hashlib.sha256()
    for rel, value in sorted(files.items()):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(value.encode("ascii"))
        digest.update(b"\n")
    return Snapshot(dict(sorted(files.items())), digest.hexdigest())


def assert_no_overlap(source: Path) -> None:
    if source.is_symlink():
        raise PublishError("PublicVault 根目录不得是符号链接")
    source = source.resolve(strict=True)
    site = SITE_ROOT.resolve(strict=True)
    if source == site or source in site.parents or site in source.parents:
        raise PublishError("PublicVault 与网站工程不得相同或互相包含")


def source_paths(source: Path) -> list[tuple[Path, str]]:
    unexpected: list[str] = []
    selected: list[tuple[Path, str]] = []

    for entry in sorted(source.iterdir(), key=lambda item: item.name):
        if entry.name in IGNORED_ROOT_NAMES:
            continue
        if entry.is_symlink():
            raise PublishError(f"发现符号链接：{entry.name}")
        if entry.name.startswith("."):
            unexpected.append(entry.name)
        elif entry.is_file() and entry.name in ALLOWED_TOP_FILES:
            selected.append((entry, entry.name))
        elif entry.is_dir() and entry.name in ALLOWED_TOP_DIRS:
            for current, dirs, files in os.walk(entry, followlinks=False):
                current_path = Path(current)
                for name in tuple(dirs) + tuple(files):
                    candidate = current_path / name
                    rel = candidate.relative_to(source).as_posix()
                    if candidate.is_symlink():
                        raise PublishError(f"发现符号链接：{rel}")
                    if name.startswith(".") or name in {"Thumbs.db", ".DS_Store"}:
                        raise PublishError(f"公开目录内存在隐藏或系统文件：{rel}")
                for name in files:
                    candidate = current_path / name
                    rel = candidate.relative_to(source).as_posix()
                    if candidate.suffix.lower() not in ALLOWED_SUFFIXES:
                        raise PublishError(f"不允许的公开文件类型：{rel}")
                    selected.append((candidate, rel))
        else:
            unexpected.append(entry.name)

    if unexpected:
        joined = ", ".join(unexpected)
        raise PublishError(f"PublicVault 根目录包含未列入发布白名单的项目：{joined}")
    if not any(rel == "index.md" for _, rel in selected):
        raise PublishError("PublicVault 必须包含 index.md")
    return sorted(selected, key=lambda item: item[1])


def snapshot_source(source: Path) -> Snapshot:
    return make_snapshot({rel: file_hash(path) for path, rel in source_paths(source)})


def snapshot_target(target: Path) -> Snapshot:
    if not target.exists():
        return make_snapshot({})
    if target.is_symlink() or not target.is_dir():
        raise PublishError("content 必须是普通目录，不能是符号链接")
    if not (target / MARKER).is_file() or (target / MARKER).is_symlink():
        raise PublishError("content 缺少管理标记；拒绝覆盖未知目录")

    files: dict[str, str] = {}
    for current, dirs, names in os.walk(target, followlinks=False):
        current_path = Path(current)
        for name in tuple(dirs) + tuple(names):
            path = current_path / name
            rel = path.relative_to(target).as_posix()
            if path.is_symlink():
                raise PublishError(f"content 中发现符号链接：{rel}")
            if name.startswith(".") and rel != MARKER:
                raise PublishError(f"content 中发现未知隐藏项目：{rel}")
        for name in names:
            path = current_path / name
            rel = path.relative_to(target).as_posix()
            if rel == MARKER:
                continue
            files[rel] = file_hash(path)
    return make_snapshot(files)


def load_manifest() -> Snapshot:
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublishError(f"无法读取发布清单：{exc}") from exc
    if data.get("schema") != 1 or not isinstance(data.get("files"), dict):
        raise PublishError("发布清单格式无效")
    snapshot = make_snapshot({str(k): str(v) for k, v in data["files"].items()})
    recorded = str(data.get("tree_digest", ""))
    if recorded and recorded != snapshot.tree_digest:
        raise PublishError("发布清单摘要无效，拒绝继续")
    return snapshot


def validate_target_against_manifest(target: Snapshot, manifest: Snapshot) -> None:
    if target.files != manifest.files:
        raise PublishError(
            "content 与上次发布清单不一致；可能有人直接编辑了发布副本。"
            "请不要覆盖，先检查 git diff"
        )


def copy_candidate(source: Path, stage: Path) -> Snapshot:
    stage.mkdir(parents=True)
    (stage / MARKER).write_text(
        "Generated from PublicVault. Do not edit this directory directly.\n", encoding="utf-8"
    )
    files: dict[str, str] = {}
    for path, rel in source_paths(source):
        destination = stage / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination, follow_symlinks=False)
        destination.chmod(0o644)
        files[rel] = file_hash(destination)
    return make_snapshot(files)


def validate_local_references(root: Path) -> None:
    problems: list[str] = []
    for markdown in root.rglob("*.md"):
        rel = markdown.relative_to(root).as_posix()
        text = markdown.read_text(encoding="utf-8")
        refs = [match.group(1).strip().split()[0].strip("<>") for match in INLINE_LINK_RE.finditer(text)]
        refs += [match.group(1).strip() for match in WIKILINK_RE.finditer(text)]
        for raw in refs:
            value = unquote(raw).replace("\\", "/")
            if not value or value.startswith(("#", "http://", "https://", "mailto:")):
                continue
            if value.lower().startswith("file:"):
                problems.append(f"{rel}: file:// 引用")
            elif value.startswith(("/", "~/")) or re.match(r"^[A-Za-z]:/", value):
                problems.append(f"{rel}: 绝对路径引用")
            elif any(part == ".." for part in Path(value.split("#", 1)[0]).parts):
                problems.append(f"{rel}: 父目录越界引用")
    if problems:
        raise PublishError("发现不允许的本地引用：\n  - " + "\n  - ".join(problems))


def diff_snapshots(old: Snapshot, new: Snapshot) -> tuple[list[str], list[str], list[str]]:
    old_names, new_names = set(old.files), set(new.files)
    added = sorted(new_names - old_names)
    deleted = sorted(old_names - new_names)
    modified = sorted(name for name in old_names & new_names if old.files[name] != new.files[name])
    return added, modified, deleted


def print_preview(old: Snapshot, new: Snapshot) -> bool:
    added, modified, deleted = diff_snapshots(old, new)
    print("\n发布预览")
    for label, values in (("ADD", added), ("MODIFY", modified), ("DELETE", deleted)):
        print(f"\n{label}:")
        if values:
            for value in values:
                print(f"  {value}")
        else:
            print("  (none)")
    print(f"\n汇总：{len(added)} 新增，{len(modified)} 修改，{len(deleted)} 删除")
    print(f"内容摘要：{new.tree_digest}")
    return bool(added or modified or deleted)


def write_manifest(snapshot: Snapshot) -> None:
    data = {"schema": 1, "tree_digest": snapshot.tree_digest, "files": snapshot.files}
    temporary = MANIFEST_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, MANIFEST_PATH)


def atomic_install(stage: Path, snapshot: Snapshot) -> None:
    backup = SITE_ROOT / f".publish-backup-{uuid.uuid4().hex}"
    old_manifest = MANIFEST_PATH.read_bytes()
    os.replace(CONTENT_ROOT, backup)
    try:
        os.replace(stage, CONTENT_ROOT)
        write_manifest(snapshot)
    except Exception:
        failed = SITE_ROOT / f".publish-stage-failed-{uuid.uuid4().hex}"
        if CONTENT_ROOT.exists():
            os.replace(CONTENT_ROOT, failed)
        os.replace(backup, CONTENT_ROOT)
        MANIFEST_PATH.write_bytes(old_manifest)
        if failed.exists():
            shutil.rmtree(failed)
        raise
    else:
        shutil.rmtree(backup)


def read_source_from_config() -> Path:
    if not CONFIG_PATH.exists():
        raise PublishError(
            "缺少 config/publish.local.toml；请复制 publish.example.toml 并填写 PublicVault 绝对路径"
        )
    with CONFIG_PATH.open("rb") as handle:
        data = tomllib.load(handle)
    raw = data.get("public_vault")
    if not isinstance(raw, str) or not Path(raw).is_absolute():
        raise PublishError("public_vault 必须是绝对路径")
    source = Path(raw)
    if not source.exists() or not source.is_dir():
        raise PublishError(f"PublicVault 不存在或不是目录：{source}")
    assert_no_overlap(source)
    return source.resolve(strict=True)


def run(mode: str) -> int:
    source = read_source_from_config()
    manifest = load_manifest()
    target_before = snapshot_target(CONTENT_ROOT)
    validate_target_against_manifest(target_before, manifest)

    temp_root = Path(tempfile.mkdtemp(prefix=".publish-stage-", dir=SITE_ROOT))
    stage = temp_root / "content"
    try:
        candidate = copy_candidate(source, stage)
        findings = scan_tree(stage)
        if findings:
            raise PublishError(format_findings(findings))
        validate_local_references(stage)
        changed = print_preview(target_before, candidate)
        if not changed:
            print("\n没有需要发布的变化。")
            return 0
        if mode == "dry-run":
            print("\ndry-run 完成：未修改 content、Git 或远端。")
            return 0

        print("\n以上文件将进入公开网站与公开 Git 历史。")
        if input("继续复制到网站工程？[y/N] ").strip().lower() != "y":
            print("已取消；未修改正式 content。")
            return 3

        source_after = snapshot_source(source)
        target_after = snapshot_target(CONTENT_ROOT)
        if source_after != candidate:
            raise PublishError("确认后 PublicVault 已变化；旧确认失效，请重新 dry-run")
        if target_after != target_before:
            raise PublishError("确认后 content 已变化；旧确认失效，请检查后重试")

        atomic_install(stage, candidate)
        print("\n本地发布副本已更新。尚未 commit 或 push。")
        print("下一步：运行 `python3 scripts/release.py --dry-run`。")
        return 0
    finally:
        if temp_root.exists():
            shutil.rmtree(temp_root)


def main() -> int:
    parser = argparse.ArgumentParser(description="PublicVault 到 Quartz content 的安全单向发布")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="只扫描并显示差异")
    group.add_argument("--publish", action="store_true", help="确认后更新本地发布副本")
    args = parser.parse_args()
    try:
        return run("publish" if args.publish else "dry-run")
    except (OSError, PublishError, tomllib.TOMLDecodeError) as exc:
        print(f"发布已阻断：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
