# Architecture

`PublicVault` and this repository are siblings, not nested repositories. PublicVault is the only editable source of articles. The `content/` tree is a complete generated snapshot used by Quartz and GitHub Actions.

```text
PublicVault --validated one-way copy--> content --Quartz--> public --Pages--> Web
```

The copy boundary is implemented in `scripts/publish.py`. It reads one explicit path from the Git-ignored local TOML file, creates a temporary candidate, computes SHA-256 per file and for the whole tree, scans the candidate, shows a three-way diff, asks for confirmation, rechecks source and target, then swaps the directory. `config/published-manifest.json` detects direct edits and unknown target files.

Git and network publication are deliberately outside that operation. `scripts/release.py` accepts only changes under `content/` and the manifest, then tests, builds, scans the generated `public/` tree, confirms commit, and confirms push separately.

GitHub Actions rebuilds from reviewed repository content. It has read-only repository permission in the build job; only the deploy job receives Pages and OIDC write permissions.
