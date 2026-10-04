# Security model

## Privacy boundary

Private Vault is out of scope and inaccessible by design: no path is configured, no discovery runs, and no code imports from it. Moving material into PublicVault is a conscious manual act. Every visible file in PublicVault should be treated as potentially public.

## Implemented controls

- Explicit source path kept only in an ignored local configuration.
- Allowlisted top-level content and file types.
- Rejection of symbolic links, junction-like traversal, source/target overlap, absolute local references, `file://` references and parent-directory references.
- Value-redacting scans for common private keys, tokens and credential assignments.
- Manifest-based detection of direct edits or unknown files in the generated copy.
- Preview with additions, modifications, deletions and a SHA-256 tree digest.
- Revalidation after confirmation and atomic replacement with recovery on failure.
- Separate confirmations for local copy, Git commit and public push.
- CI scans both source content and final generated output before deployment.

## Reviewed dependency advisory

The Quartz build uses `globby → fast-glob → micromatch → braces`. The high-severity [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) currently has no patched `braces` release. In this project, glob patterns are fixed by repository code and configuration; the generated GitHub Pages site is static and does not run this dependency for visitors.

`scripts/audit_dependencies.py` permits only this exact advisory, dependency chain and locked versions. Every other high or critical advisory, a changed chain, or a changed version fails the local release and CI. Remove the exception when an upstream patched version is available. A patched moderate-severity `brace-expansion` version is already locked.

These controls reduce accidental disclosure; they cannot recognize every private fact, sensitive text inside images/PDFs, or a malicious process that already has local write access. Human review remains mandatory.

## If a secret is published

Stop publishing, revoke or rotate the credential first, and treat the value as compromised. A normal website rollback does not erase Git history, forks, downloads, logs or caches. Escalate to a high-intelligence security review before any history rewrite or provider-specific purge.
