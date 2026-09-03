# Security policy

## Supported versions

There is no supported public release yet. The `main` branch of this repository and exact
native artifacts produced from it receive security fixes during technical-alpha
development. Older commits, local modifications, third-party packs, and the web
preview are not independently supported versions.

## Report privately

Do not open a public issue, discussion, or pull request for a suspected
vulnerability. Repository collaborators should use a private draft security
advisory from the repository Security tab or contact the lead maintainer through
the established private project channel. Before public cutover, GitHub private
vulnerability reporting must be enabled and verified at:

<https://github.com/Omega-Omarchy/omega-omarchy/security/advisories/new>

Include the affected commit/artifact digest, platform, reproduction, impact,
whether untrusted files or network access are required, and any safe diagnostic
output. Do not include real secrets or private user data; coordinate a secure
transfer if they are essential.

The target response is acknowledgment within three business days and an initial
severity/scope decision within seven. Timelines for a fix and coordinated
disclosure depend on impact and reproducibility. No bounty is currently offered.

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
