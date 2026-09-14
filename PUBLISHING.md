# Publishing and operations

## One-time local setup

Use Node.js 24 (see `.node-version`) with npm 10.9.2 or newer. Node.js 25 is intentionally rejected because it caused abnormal memory growth in the Quartz build tested for this project.

The checked-in example is safe to share. The real file is ignored:

```text
config/publish.example.toml
config/publish.local.toml
```

The local file already points to the sibling PublicVault in this workspace. On another computer, copy the example and set an absolute PublicVault path. Never configure a Private Vault path.

## Publish content locally

From `personal-site/`:

```bash
python3 scripts/publish.py --dry-run
python3 scripts/publish.py --publish
python3 scripts/release.py --dry-run
```

The first command is non-mutating. The second asks before replacing `content/` and never commits or pushes. The third runs all local gates without committing or pushing.

## Connect GitHub and Pages

1. Create an empty public GitHub repository, normally `personal-site`; do not initialize it with files.
2. Configure the canonical Pages URL:

   ```bash
   python3 scripts/configure_site.py --github-user YOUR_NAME --repository personal-site
   ```

3. Commit that setup change, then set your own remote:

   ```bash
   git remote add origin git@github.com:YOUR_NAME/personal-site.git
   git push -u origin main
   ```

4. In GitHub repository Settings → Pages, set Source to **GitHub Actions**.
5. For normal content releases, use:

   ```bash
   python3 scripts/release.py --release --push
   ```

The tool shows managed changes, tests and builds locally, then asks once before commit and again before push.

## Acceptance

- Actions build and deploy jobs are green.
- Home, About and the Chinese test article open from the Pages URL.
- Search, WikiLink navigation, RSS (`index.xml`), sitemap (`sitemap.xml`) and 404 work.
- `git ls-files` contains no `publish.local.toml`, `.obsidian`, Private Vault path or credential.
- A Private Vault sentinel, symlink, parent reference and synthetic token are all blocked by tests.

## Rollback

Choose a known-good commit from the repository history, preview it, then create a new rollback commit:

```bash
python3 scripts/rollback.py --to GOOD_COMMIT
python3 scripts/rollback.py --to GOOD_COMMIT --apply --push
```

This restores only the deployed content snapshot and manifest. It does not modify PublicVault, force-push, or rewrite history. The next ordinary publication from PublicVault restores the latest source.
