# Security policy

## Supported versions

The `main` branch, the current game deployed at https://omegaomarchy.org/play/,
and the latest native artifact built from `main` receive security fixes.
Older snapshots, local modifications, and third-party content packs are not
independently maintained versions. Include the affected commit or build when
reporting an issue.

## Report privately

Do not open a public issue, discussion, or pull request for a suspected
vulnerability. Use GitHub's private vulnerability reporting form, enabled for
this public repository:

<https://github.com/Omega-Omarchy/omega-omarchy/security/advisories/new>

Include the affected commit/artifact digest, platform, reproduction, impact,
whether untrusted files or network access are required, and any safe diagnostic
output. Do not include real secrets or private user data; coordinate a secure
transfer if they are essential.

The target response is acknowledgment within three business days and an initial
severity/scope decision within seven. Timelines for a fix and coordinated
disclosure depend on impact and reproducibility. No bounty is currently offered.

## Automated checks

The repository workflows configure CodeQL for Python, JavaScript, and GitHub
Actions on pull requests, `main`, and a weekly schedule. Dependency review
rejects newly introduced known vulnerabilities, daily pip-audit jobs check
the pinned runtime/release and audit toolchains, and Dependabot proposes
weekly Python and Actions updates. The native release job also audits its
dependency inventory and builds an SBOM. These checks do not publish the game.

Maintainers should enable secret-scanning push protection and enforce the
required checks described in [GitHub setup](docs/github-setup.md). Scheduled
jobs need attention when they fail, even if there has been no recent commit.

## In scope

- Content-pack traversal, symlink, executable-content, digest, or isolation
  bypasses.
- Save/Omega Code parsing that enables arbitrary code execution, unsafe writes,
  or denial of service beyond documented limits.
- Unexpected network publication, sharing-policy bypass, or cross-profile data
  access.
- Artifact/archive extraction vulnerabilities or packaged private material.
- Credential, token, private-reference, or sensitive-history exposure.
- Omarchy/Limitless integration behavior that crosses its documented capability
  boundary.

Ordinary gameplay bugs, balance, satire/canon disagreement, supported local mod
effects, and reports requiring social engineering without a product weakness
belong in the appropriate non-security issue form.

## Safe harbor expectations

Use only accounts/data you control, minimize access, stop after demonstrating
impact, avoid persistence or service disruption, and allow reasonable repair
time before disclosure. This policy is an intent statement, not a promise that
third parties or laws grant the same protection.
