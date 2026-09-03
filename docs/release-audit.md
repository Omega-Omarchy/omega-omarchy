# Release and history audit

`tools/audit_release.py` produces a sanitized inventory of the current tracked
tree, every blob and commit reachable from local branches/tags/notes/remotes,
commit identities and messages, source archives, wheels, native bundles, web
output, source maps, Python packages, and bundled native libraries.

Matched values are never written to reports or standard output. Findings carry
only category, scope, safe locator, line when applicable, object prefix, and a
one-way fingerprint. Exceptions live in `audit/release-audit.toml` with a stable
ID and rationale; broad credential exceptions are intentionally absent.

## Exact-candidate command

Build the native artifact first, then query the Python Packaging Advisory
Database from the isolated pinned audit environment:

```bash
./scripts/omega package --require-clean --output dist/native-local

python3 -m venv dist/audit-local/audit-venv
dist/audit-local/audit-venv/bin/python -m pip install \
  --requirement requirements/bootstrap.txt
dist/audit-local/audit-venv/bin/python -m pip install \
  --requirement requirements/audit-tool.txt
dist/audit-local/audit-venv/bin/python -m pip_audit \
  --requirement requirements/audit-targets.txt \
  --no-deps --disable-pip --format json \
  --output dist/audit-local/pip-audit.json

./scripts/omega web
./scripts/omega audit-release \
  --require-clean \
  --build-distributions \
  --vulnerability-report dist/audit-local/pip-audit.json \
  --artifact native=dist/native-local/omega-omarchy-0.1.0-linux-x86_64.tar.gz \
  --artifact web=dist/web
```

CI runs the same dependency query and audit after its clean artifact verifier.
Known vulnerabilities fail before report generation. The history scanner runs
in report-only mode while the explicitly recorded historical-path finding is
unresolved; credentials, unsafe archives, packaging failures, dependency
advisories, and native verifier failures still fail their owning steps.

Outputs under ignored `dist/audit-local/` are:

- `release-audit.json` — complete sanitized machine record;
- `release-audit.md` — human review surface;
- `sbom.spdx.json` — SPDX 2.3 Python package inventory; and
- `pip-audit.json` — advisory query result.

## Manual and external boundary

The local scanner cannot prove the state of hidden/deleted remote refs, issues,
discussions, organization audit logs, credential providers, legal permissions,
or all platform-native libraries. Before cutover, export and scan GitHub Actions
logs and release objects, review remote repository settings, run an appropriate
native-library vulnerability scanner, and have a second person inspect the
configuration, allowlist, sampled blobs/binaries, and exact-candidate report.

Record the sanitized findings, exceptions, and second-reviewer sign-off in the
cutover evidence index. Do not reproduce matched secrets in that record.
