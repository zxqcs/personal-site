# Agent operating rules

## Immutable boundaries

- Never search for, enumerate, open, index, or modify any Private Vault.
- `../PublicVault` is the only content source. `content/` is a generated copy and must not be edited by hand.
- Never create a symlink or bidirectional sync between PublicVault and this repository.
- Never weaken a failed security check to make a publication succeed.
- Never add `config/publish.local.toml`, credentials, absolute user paths, or Private Vault data to Git.
- Never force-push or rewrite public history without explicit user approval and a security review.

## Agent allocation

- Use `gpt-5.6-luna` at low effort for bounded mechanical work: inventory, formatting, routine tests, file-list comparisons, and log summaries.
- Use `gpt-5.6-terra` or `gpt-5.6-sol` for ordinary implementation and Quartz compatibility fixes.
- Reserve `gpt-6-astra` with high effort for architecture, privacy/security decisions, suspected credential exposure, destructive recovery, and ambiguous failures.
- Low-cost agents may report a failed gate but may not waive it or decide that suspicious material is safe to publish.

## Required workflow

1. Edit prose only in PublicVault.
2. Run `python3 scripts/publish.py --dry-run`.
3. Review every add, modify, and delete plus the content digest.
4. Run `python3 scripts/publish.py --publish` and confirm.
5. Run `python3 scripts/release.py --dry-run`.
6. Only after review, run `python3 scripts/release.py --release --push`; commit and push have separate confirmations.
