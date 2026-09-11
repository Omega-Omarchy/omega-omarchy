# Public GitHub setup

The configuration is adapted from `Univeracity/vyral` for this Python game and
plain-JavaScript website. Omega has no managed worker containers or npm package,
so it does not copy Vyral's container publishing, cloud credentials, or
multi-language SDK qualification jobs.

## Checks supplied by the repository

| Workflow | Purpose | Trigger |
| --- | --- | --- |
| CI | Python 3.11/3.12 tests, deterministic assets, website/editor checks, native packaging and verification | Pull requests, main, manual |
| CodeQL | Python, JavaScript/TypeScript, and Actions source analysis | Pull requests, main, weekly, manual |
| Dependency Review | Reject newly introduced dependencies with known vulnerabilities | Pull requests |
| Dependency Audit | Audit pinned runtime/release packages and the audit toolchain | Pull requests, main, daily, manual |
| Dependabot | Propose Python and GitHub Actions updates | Weekly; security updates when alerts are available |

Actions are pinned to full commit hashes. Jobs use read-only repository access
except CodeQL's scoped security-results permission. Pull-request workflows use
GitHub-hosted runners without deployment secrets, persisted Git credentials,
or `pull_request_target`. Dependency Review does not require permission to
write public PR comments. No workflow deploys the site or automatically merges
an update.

CodeQL excludes exported builds, local environments, and vendored code to avoid
scanning duplicate copies. Native dependency inventories and pip-audit cover
the pinned Python release surface separately. Optional audio-authoring and
Limitless dependencies are not part of the shipped runtime audit inventory;
Dependabot can still propose changes to their `pyproject.toml` declarations.

## Settings checked on September 11, 2026

Read-only inspection of `Omega-Omarchy/omega-omarchy` found:

- Public visibility, `main` default branch, Issues and Discussions enabled.
- Actions enabled; private vulnerability reporting enabled.
- Dependabot security updates and secret scanning enabled.
- CodeQL default setup not configured.
- Secret-scanning push protection disabled.
- **Default Ruleset** present but disabled. It currently includes one required
  approval, deletion/force-push protection, linear history, and PR resolution.

No GitHub settings were changed by this preparation pass. The new workflow
files become active when committed and pushed; scheduled jobs and Dependabot
configuration must reach the default branch. Local validation does not mean
GitHub has already run CodeQL or that repository rules are enforced.

## Maintainer actions

1. **Commit and publish the intended launch tree.** Include the new `.github/`
   files, README/docs, accepted source and runtime assets, and the website source.
   Leave machine-local captures, credentials, environments, and transient build
   directories out. Keep the existing source-code/asset license distinction.
2. In [Code security settings](https://github.com/Omega-Omarchy/omega-omarchy/settings/security_analysis),
   enable **Secret scanning → Push protection**. Keep dependency graph,
   Dependabot alerts/security updates, and private vulnerability reporting on.
3. Use the committed **advanced CodeQL workflow**. Do not also enable CodeQL
   default setup; it can conflict with uploading results from the custom workflow.
   After the files reach `main`, run CI, CodeQL, and Dependency Audit from
   [Actions](https://github.com/Omega-Omarchy/omega-omarchy/actions) and review
   [Security](https://github.com/Omega-Omarchy/omega-omarchy/security).
4. In [repository rules](https://github.com/Omega-Omarchy/omega-omarchy/settings/rules),
   edit **Default Ruleset**, target the default branch, and change enforcement
   to **Active** after the first successful runs. Require PRs, block deletions
   and force pushes, require resolved conversations, and add the checks below.
   Only select actual check names offered after a successful run.
5. Choose a review policy that works for the maintainer team. With Jeremy as
   the only code owner, requiring another approval blocks his own PRs unless a
   deliberate maintainer bypass is configured. Use zero required approvals for
   a sole-maintainer workflow, or one when another trusted reviewer is available.
   Require code-owner review only once that arrangement is workable.
6. Leave the default workflow token permission at **Read repository contents**,
   keep write-token access to fork workflows off, and require approval for
   first-time external contributors' workflows. If the organization restricts
   Actions, allow `actions/*` and `github/codeql-action/*`.
7. Watch scheduled workflow failures and Dependabot alerts. Public repositories
   can have scheduled Actions disabled after 60 days without activity; re-enable
   them if GitHub pauses them. This setup does not add an external alerting service.

Recommended required checks:

- `Test and deterministic gates (Python 3.11)`
- `Test and deterministic gates (Python 3.12)`
- `Website and editor checks`
- `Native Linux artifact`
- `Analyze python`
- `Analyze javascript-typescript`
- `Analyze actions`
- `Review dependency changes`
- `Audit pinned Python dependencies`

The native release build needs full Git history for contributor attribution.
CI creates `.venv` and installs with `.venv/bin/python`, matching `scripts/omega`.
The test matrix also installs optional audio-authoring extras into that same
environment and imports librosa, scipy, and soundfile before the release gate.
Those extras are excluded from the native artifact job.
Generated credits are written into the staged browser/native package; they do
not dirty the source checkout. The web release audit uses an ignored output
folder. CI checks regenerated art/audio against their tracked source outputs;
it does not compare a current-commit web bundle with a committed parent bundle
whose embedded credits necessarily mention a different Git revision.

## Local validation

```sh
./scripts/omega test tests/test_credits.py tests/test_web.py tests/test_release_artifact.py tests/test_release_audit.py
node --test website/motion.test.mjs website/news.test.mjs tests/level_editor_state.test.cjs
.venv/bin/python -m unittest discover -s website -p 'test_*.py'
./scripts/omega website
.venv/bin/python website/check.py
```

Run `actionlint` after workflow changes. For a release candidate, run the full
`./scripts/omega release-check` and build/verify a native artifact from a clean
checkout. The dependency audit uses the isolated toolchain pinned in
`requirements/audit-tool.txt`; do not add audit tools to the game's runtime.

## Preparation verification — September 11, 2026

The broad local Python run completed with 539 passing tests and one expected
skip, exposing five failures: two stale prologue/credit-input expectations and
three missing optional audio-authoring dependencies. The expectations and CI
setup were corrected, and all five affected tests passed on rerun. A separate
52-test credits/web/release scope passed, as did 30 browser/editor tests, two
News build tests, workflow lint, configuration YAML parsing, and website export
validation. Both pinned Python audit inventories reported no known vulnerabilities.

A native artifact built in an isolated release environment passed the extracted
artifact verifier. Its credits were checked against the current Git revision.
The launcher now suppresses the SDL support banner so `--version` remains
machine-readable. The local checkout contains ongoing launch work, so this is
not a claim that a clean-commit GitHub run has already passed; run the committed
workflows before enabling their required status checks.

References: [GitHub CodeQL workflow configuration](https://docs.github.com/en/code-security/reference/code-scanning/workflow-configuration-options),
[dependency review](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review),
[Dependabot options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference),
and [scheduled workflow behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
