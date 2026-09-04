# Open-source cutover: design and invariant gates

| Field | Value |
|---|---|
| Status | **Proposed; public cutover is currently NO-GO** |
| Decision owner | Founder / lead maintainer |
| Target release | **Omega Omarchy 0.2 — Open Development Alpha** |
| Release scope | A polished 10–15 minute Chapter 1 vertical slice and a real contribution surface |
| Last updated | 2026-09-02 |

This document defines the conditions under which the private Omega Omarchy
repository may become a founder-led open-source project. It is a release gate,
not authorization to change repository visibility. Even after every technical
gate passes, the founder must separately authorize the public cutover.

The intended first public impression is: **this is already a real game that I
can enjoy and help expand**. It must not feel like an ambitious prototype that
the public is being asked to finish.

## Decision

Do not make the repository public today. Complete one focused milestone, then
release it as **Omega Omarchy 0.2 — Open Development Alpha** with direction and
canon remaining explicitly maintainer-led.

Do not wait for all six chapters. The cutover target is a coherent, polished
Chapter 1 that takes a first-time player roughly 10–15 minutes and demonstrates
the intended movement, art, humor, conversion combat, customization, and
procedural identity of the game.

## How the gate works

Every gate marked **MUST** is an invariant. A gate passes only when:

1. every checkbox in the gate is complete;
2. its evidence is committed or attached to a durable release record;
3. the evidence was produced from the exact release candidate commit; and
4. the evidence has been reviewed by someone other than its implementer where
   the checklist calls for independent review.

Use these status values in the gate ledger:

- **OPEN** — required work or evidence is absent.
- **PARTIAL** — a credible implementation exists, but the invariant is not
  fully demonstrated.
- **PASS** — all acceptance checks and evidence requirements are satisfied.
- **REGRESSED** — a formerly passing invariant no longer holds. This is an
  immediate cutover blocker.

There are no silent waivers. A changed requirement must be recorded as a design
decision in this document before the gate may pass. “It is an alpha” is not a
waiver for a broken installer, unclear rights, leaked private material, an
unplayable chapter, or a simulated integration.

## Global invariants

These conditions apply across every gate:

- [ ] **Private until explicitly authorized.** No script, CI workflow, release
  job, or contributor can change repository visibility or announce the game.
- [ ] **Evidence before claims.** Public copy is limited to behavior shown by
  the release candidate and reconciled with README and release-notes claims.
- [ ] **Chapter 1 is the product boundary.** The default build ends Chapter 1
  cleanly. Later-chapter scaffolding is hidden behind an honest development
  boundary and is never presented as a finished campaign.
- [ ] **Offline remains first-class.** Ordinary local play and content-pack use
  do not require Limitless, an account, or network access.
- [ ] **Sharing remains explicit.** Nothing is published merely because it was
  created, saved, queried, or adopted. The saved sharing policy and the
  per-publish confirmation both fail closed.
- [ ] **Determinism remains bound.** Seed, generator/schema version, ordered
  content-pack identities, digests, difficulty, and accessibility settings
  continue to identify a world reproducibly.
- [ ] **Mods are data by default.** A content pack cannot execute arbitrary code
  or write outside game-owned storage merely by being installed or inspected.
- [ ] **Rights are scoped, not implied.** A code license does not grant rights
  in third-party marks, names, likenesses, or separately licensed assets.
- [ ] **Founder-led means founder-led.** Public participation expands execution
  and content breadth; it does not convert the central voice, canon, or product
  direction into a vote.

## Current gate ledger

This is the baseline assessment from the tracked tree and the 2026-09-02
evidence matrix. A status is not upgraded on implementation alone; the listed
acceptance evidence must exist.

| Gate | Invariant | Current status | Current evidence / gap |
|---|---|---:|---|
| G0 | Scope, authority, and claim discipline | **PARTIAL** | Private-alpha language exists. A founder-authorized cutover record and final public-claim review do not. |
| G1 | Polished 10–15 minute Chapter 1 | **PARTIAL** | Chapter 1 has an automated ordinary-input golden path, a dedicated completion/credits boundary, save restoration at that boundary, live reversible editing, visible overload/retry, confirmed archived reroll, and an explicitly labelled opt-in for later development chapters. Duration, first-time-player enjoyment, pacing, controller hardware, and release-level polish are not independently qualified. |
| G2 | Clean-clone install and playable artifact | **PARTIAL** | A portable native archive now embeds the interpreter/runtime/assets/core pack; records commit, dependencies, rights files and asset digest; emits SHA-256; and passes safe extraction plus an isolated-profile headless smoke locally and in hosted CI. Account storage quota prevented hosted retention, and independent clean-machine install/play evidence remains absent. |
| G3 | CI and contribution surface | **PARTIAL** | Read-only CI passed the full gate on hosted Python 3.11/3.12 and clean artifact build/verification with immutable action pins; storage quota alone rejected artifact retention. Contribution, founder-led governance, roadmap, security, DCO, issue-dependent test scopes, triage, five issue forms, and the PR template are tracked. The project deliberately does not adopt a standalone Code of Conduct. Pull-request execution, branch protection, applied labels, private-reporting verification, and an external dry run remain absent. |
| G4 | External content-pack/mod interface | **PARTIAL** | Built-in Chapter 1 and a maintained add-on now use a versioned data-only loader, deterministic ordering, canonical digests, exact save compatibility, validator/sealer tooling, and a consent-gated directory/ZIP review/install/enable/disable/remove lifecycle in game-owned storage. Custom definitions/assets, a graphical in-game review surface, semver ranges, and later-content migration remain open. |
| G5 | License, rights, branding, and likeness | **PARTIAL** | MIT code scope, provisionally all-rights-reserved original assets/content, third-party marks, real-person likenesses, pack licenses, dependency notices, provenance requirements, and an unofficial-project disclaimer are now separated. File-level provenance, transitive binary inventory, permissions/replacements, explicit public asset license, and founder/legal review remain open. |
| G6 | Genuine cross-install Limitless exchange | **PARTIAL** | Local query, digest verification, adoption receipts, and fail-closed sharing policy exist. Create/modify → publish → remote discover → apply → verify across two isolated installations is not demonstrated. |
| G7 | Repository history and sensitive-reference audit | **PARTIAL** | A redacting preflight now inventories refs, all reachable blobs/commits, identities/messages, large objects, source/wheel/native/web artifacts, source maps, SPDX packages, native binaries, GitHub state/logs, and Python advisories. No credential signature was found and 19 dependency advisories/current magic paths were remediated. One historical machine-path fingerprint, PNG provenance sampling, native-library advisory coverage, exact-candidate rescan, and second review remain open. |
| G8 | Public positioning and media | **PARTIAL** | Development evidence screenshots and a GIF exist. A curated screenshot set, short gameplay trailer, release page, and small public roadmap do not. |
| G9 | Exact-candidate rehearsal and authorization | **OPEN** | No end-to-end public-cutover rehearsal or separate founder authorization exists. |

**Cutover rule:** G0–G9 and every global invariant must be **PASS** at the same
release-candidate commit. Any **OPEN**, **PARTIAL**, or **REGRESSED** status means
NO-GO.

## G0 — Scope, authority, and claim discipline (MUST)

The release is honest about what it is and who directs it.

- [ ] The release is named **Omega Omarchy 0.2 — Open Development Alpha**.
- [ ] README, release notes, package metadata, website copy, trailer copy, and
  in-game credits all describe Chapter 1 as the qualified playable scope.
- [ ] Chapters 2–6 are described as future development, not a shipped campaign.
- [ ] The web build is labelled a Chapter 1 browser alpha and claims only the
  browser features independently exercised at the exact candidate; full-campaign
  or cross-browser parity is not implied.
- [ ] The Omarchy panel is either exercised in its native shell and documented,
  or omitted/relabelled as an unqualified integration preview.
- [x] Project governance says the founder/lead maintainer owns product direction,
  canon, release decisions, and final merge authority.
- [x] The contribution invitation names the desired areas: art, audio,
  accessibility, level content, enemies, methods, and content packs.
- [x] The same invitation says that central voice and canon are not designed by
  committee.
- [ ] A separate, dated founder approval identifies the exact commit/tag that may
  be made public. Passing this document alone is not approval.

**Required evidence:** final claim audit, governance text, release-copy diff,
native-shell result or explicit exclusion, and signed-off cutover record.

## G1 — Polished 10–15 minute Chapter 1 (MUST)

Chapter 1 is a compact game, not a feature showroom. The installer parody,
traversal, item use, conversion combat, signature edit/customization moment,
boss, and chapter resolution form one understandable arc.

### Play and pacing

- [ ] A new player can start the release artifact, understand the controls, and
  finish Chapter 1 without source access, debug keys, or verbal rescue.
- [ ] At least five first-time-player sessions are observed on the release
  candidate; at least four finish without intervention.
- [ ] Median first completion time is 10–15 minutes. Outliers and restarts are
  recorded rather than discarded.
- [ ] At least four of five testers answer yes to “I would voluntarily play the
  next chapter.” Notes explain the answer and drive a final friction pass.
- [ ] The chapter has a readable beginning, escalation, boss payoff, and ending;
  it does not dump the player into Chapter 2 scaffolding.
- [ ] At least three materially different seeds are human-played to completion.
  Procedural variation changes the route without breaking pacing or narrative
  beats.

### Feel and presentation

- [ ] Movement, jumping, climbing, crouch/slide, attacks, and item use animate
  correctly and feel responsive on keyboard and gamepad.
- [ ] The Chapter 1 background, terrain, sprites, interface, text, effects,
  audio, and combat scene meet the intended quality at sixteen-bit, High, and
  Ultra fidelity.
- [ ] Fidelity changes presentation only; collision and visual gameplay
  footprint stay invariant.
- [ ] CRT remains an optional scanline/bloom treatment with independent
  scanline, curvature, and phosphor controls; it does not corrupt tint,
  scaling, readability, collision presentation, or the 60 FPS frame budget at
  any fidelity on the minimum target hardware.
- [ ] The signature fly-away/edit sequence uses its dedicated model, hides the
  traversal sprite, keeps the selector in view, and produces a useful reward.
- [ ] Combat reads as a staged RPG encounter, gives both sides turns and visible
  deltas, and returns safely to traversal.
- [ ] Interface text is fitted, shortened, paged, or scrolled; no meaningful text
  is clipped at supported window sizes and fidelity tiers.
- [ ] No placeholder, duplicated parallax layer, visibly malformed animation,
  accidental repeated background, or temporary developer copy appears in the
  Chapter 1 path.

### Reliability and accessibility

- [ ] The automated ordinary-input golden path passes from clean state.
- [ ] Save/load, reroll, pause, item selection, death/retry, boss completion, and
  chapter completion are exercised from player-visible interfaces.
- [ ] Default, precision-assist, reduced-motion, clean, and CRT configurations
  are spot-checked; accessibility settings cannot make the chapter unwinnable.
- [ ] No critical or high-severity defect remains. Accepted lower-severity issues
  are public, narrowly described, and do not undermine the chapter promise.
- [ ] Startup, generation, frame pacing, and memory budgets are written down and
  met on one ordinary Linux machine and one lower-cost target. The current
  sub-second local startup measurement is retained or any regression explained.

**Required evidence:** anonymized playtest record, timing summary, issue list,
automated test result, three-seed receipts, keyboard/gamepad matrix, performance
record, and final screenshots for all fidelity/display combinations.

## G2 — Clean-clone install and playable release artifact (MUST)

A player must not need a developer checkout to evaluate the game.

- [ ] A clean clone on every supported development platform follows the README
  exactly and reaches tests plus native play without undocumented packages,
  local paths, caches, or generated secrets.
- [ ] CI produces at least one self-contained, player-facing Linux artifact
  suitable for Omarchy (for example, an archive or AppImage with a launcher and
  runtime dependencies).
- [x] Installing and launching that artifact does not require Git, a compiler,
  editable Python install, repository checkout, or network access.
- [x] Assets needed at runtime are present; the expensive offline asset build is
  not accidentally triggered during launch.
- [x] The artifact includes version, commit identity, code/asset license files,
  third-party notices, credits, controls, and a concise support link.
- [x] Save/config/cache locations follow platform conventions and uninstalling
  the artifact does not remove user data without an explicit choice.
- [ ] The artifact is tested from a clean VM or container-like system that did
  not build it.
- [ ] SHA-256 checksums are published. Rebuilding the same tag is either
  reproducible or documented with a precise list of nondeterministic inputs.
- [ ] The Chapter 1 web build, if shipped, cannot be mistaken for the complete
  native game and links to the supported artifact.

**Required evidence:** clean-clone transcript, build workflow URL, artifact and
checksum, clean-environment install/play capture, dependency manifest, and
uninstall/save-data result.

## G3 — CI and contribution surface (MUST)

The public repository explains how to participate and automatically protects
the invariants it can test.

- [ ] GitHub CI runs on pull requests and the default branch from a clean
  environment with pinned dependencies.
- [ ] CI runs unit, generation, deterministic identity, save/load, content-pack,
  Limitless policy, packaging, and ordinary-input golden-path tests.
- [ ] CI builds the player-facing release artifact and retains enough output to
  diagnose failures.
- [ ] Branch protection requires passing checks and review; release credentials
  are unavailable to untrusted pull-request code.
- [x] `CONTRIBUTING.md` covers setup, tests, style, generated assets, content
  packs, review expectations, licenses/provenance, and the maintainer-led model.
- [ ] `SECURITY.md` provides a private reporting route, supported versions,
  response expectations, and examples of in-scope risks.
- [x] Issue forms exist for bugs, accessibility, content packs/levels, art/audio,
  and feature proposals; they request versions, seeds, receipts, and provenance
  where applicable.
- [x] A pull-request template asks for scope, tests, screenshots/audio evidence,
  deterministic impact, rights/provenance, and breaking pack/schema changes.
- [x] The inbound contribution policy is explicit. DCO sign-off is the recorded
  mechanism for accepting public patches; moderation and contribution
  acceptance remain maintainer decisions under `GOVERNANCE.md`, without a
  standalone Code of Conduct.
- [x] A small `ROADMAP.md` separates near-term accepted direction from ideas that
  are exploratory or out of scope.
- [ ] Labels and triage rules distinguish bugs, content opportunities, design
  proposals, good first issues, and maintainer-decision-needed work.

**Required evidence:** tracked community files, protected-branch screenshot or
API record, green PR workflow, artifact workflow, and a dry-run contribution
made through the documented path.

## G4 — External content-pack and mod interface (MUST)

Adding ordinary community content must not require editing a shared monolithic
Python registry. Built-in Chapter 1 content must use the same public loader and
validation rules as third-party content so the interface is exercised by every
test and release.

### Target interface

Each pack is a directory or archive with a declarative manifest and content:

```text
example-pack/
├── pack.toml
├── chapters/
├── chunks/
├── encounters/
├── dialogue/
├── assets/
├── locales/
├── LICENSE
└── ATTRIBUTION.md
```

The exact names may evolve before 0.2, but the following properties may not:

- [ ] A versioned schema defines pack ID, version, compatible game/schema range,
  dependencies, ordering constraints, licenses, authorship, content digests,
  entry points, and optional homepage/source metadata.
- [ ] Levels, chunks, entity placement, dialogue, encounters, item/enemy
  definitions, and asset references are external data rather than required edits
  to `content.py`.
- [x] The built-in Chapter 1 pack loads through the public pack loader. Core code
  contains engine rules and schema types, not the only copy of game content.
- [ ] A documented `validate-pack` command checks schema, paths, digests, rights
  metadata, deterministic ordering, reachability, unsupported features, size
  limits, and unsafe content before activation.
  The current command covers the schema, explicit license/attribution files,
  entry-point declarations, digests, supported features, and safety/size limits;
  complete cross-file asset/reference reachability remains open.
- [x] Validation rejects path traversal, absolute paths, symlink escapes,
  undeclared files, duplicate IDs, incompatible versions, digest mismatches, and
  executable content unless a future capability system explicitly allows it.
- [x] Enabling multiple packs has a deterministic order and deterministic
  conflict behavior. Load order is included in the world identity.
- [x] Missing, removed, incompatible, or corrupt packs fail safely. Saves report
  the exact missing identity and never silently substitute different content.
- [x] Pack schema compatibility and migration policy are documented. Breaking
  changes require a schema-version change and a migration or clear rejection.
- [x] Pack discovery and installation require explicit user action and show
  source, version, requested capabilities, and license before activation.
- [x] At least one small example pack is maintained outside the built-in content
  directory and passes the same validator and generation tests.
- [x] A contributor can create, validate, install, disable, and remove the example
  pack using only public documentation.

### Compatibility contract

The stable 0.2 contract is deliberately narrow: declarative content, original
assets, deterministic generation inputs, and game-owned storage. Arbitrary
Python plugins, host shell commands, unrestricted network access, and mutation
of the base installation are outside the 0.2 mod interface.

**Required evidence:** published schema/reference, built-in pack migration,
loader and adversarial validator tests, example pack, authoring tutorial,
save-compatibility tests, and a clean-install pack walkthrough.

## G5 — License, rights, branding, and likeness (MUST)

This is a rights-clearance gate, not a conclusion that attribution alone is
permission. Ambiguous material is licensed, replaced, or excluded before
cutover.

- [x] The root licensing surface distinguishes at least: source code;
  first-party original assets; third-party assets; trademarks/wordmarks; names
  and likenesses; documentation; and community content packs.
- [ ] The code license is explicit and matches package metadata and source-file
  headers where used.
- [ ] Original art, animation, audio, writing, and generated source assets have
  an explicit asset license and a provenance record sufficient for redistribution
  and contribution review.
- [ ] The author/rights holder and public source/binary redistribution terms for
  *Make It Come Alive* are documented; otherwise its FLAC master and every
  derived Ogg are removed from the public candidate and replaced.
- [ ] `THIRD_PARTY_NOTICES.md` lists every retained third-party component and
  asset with source, version/date, license or permission basis, modifications,
  and required notice text.
- [ ] Omarchy branding is reviewed separately from source-code licensing. Its
  name, logo, and visual treatment are used only on a documented rights basis;
  attribution to the upstream repository is not treated as a trademark grant.
- [ ] The names, likenesses, voices, and recognizable depictions of real people
  are inventoried and have a documented permission/fair-use/parody rationale
  approved for this release, or are replaced.
- [ ] Private visual references remain unshipped and absent from the public Git
  history and artifacts. Derived assets have their own provenance records.
- [ ] The README, game startup/credits, package metadata, and release page carry
  a clear unofficial parody/fan-project disclaimer and do not imply endorsement,
  sponsorship, or affiliation with Omarchy, Basecamp, 37signals, or depicted
  individuals.
- [ ] The blanket MIT license is not presented as granting trademark, publicity,
  privacy, or likeness rights.
- [x] Contributions require the contributor to identify source/provenance and
  confirm the right to submit code, assets, audio, writing, and pack content.
- [ ] A final rights inventory is reviewed by the founder and, where ownership or
  parody/trademark/likeness status is ambiguous, qualified counsel before public
  distribution.

**Required evidence:** scoped license files, rights inventory, third-party
notices, asset provenance manifest, disclaimer text, contributor attestation,
and final review sign-off.

## G6 — Genuine Limitless-powered customization exchange (MUST)

The integration must demonstrate compounding customization across users, not
merely advertise the idea or query a catalog bundled with the same checkout.

- [ ] Installation A creates or materially modifies a supported customization
  or content pack through the documented player/contributor flow.
- [ ] The creator previews and validates the result locally.
- [ ] Publication requires an explicit action consistent with the saved sharing
  policy and produces an immutable identity/digest and receipt.
- [ ] The published object enters a genuine discovery surface; the test does not
  use a shared checkout, shared cache, direct file copy, or preseeded local
  catalog as a substitute for publishing.
- [ ] Installation B starts with an isolated profile and cache, discovers the
  object through Limitless, and sees origin, license, compatibility, and digest
  before applying it.
- [ ] Installation B verifies the delivered bytes and schema locally, applies the
  object, and records an adoption receipt that distinguishes delivery from
  actual use.
- [ ] The applied result is visible in game and changes the expected settings,
  content identity, or world digest without corrupting the save.
- [ ] Restarting Installation B reproduces the adopted result.
- [ ] Tampered, incompatible, withdrawn, unlicensed, or unavailable objects fail
  closed with an understandable recovery path.
- [ ] Offline play, start-fresh, abstention, local-only retention, and rollback
  continue to work.
- [ ] One automated integration test and one human-observed two-installation
  exchange cover the complete lifecycle.

**Required evidence:** publication and adoption receipts, two isolated
installation identities, discovery response, before/after digest, gameplay
capture, failure-case log, and an integration-test result from the exact
release candidate.

## G7 — Repository history and sensitive-reference audit (MUST)

Auditing only the working tree is insufficient because making a repository
public exposes reachable history, tags, branches, release artifacts, issues,
and CI logs.

- [ ] Enumerate every ref that will become public: branches, tags, notes, and
  release objects. Delete or retain each intentionally.
- [ ] Scan the current tree and all reachable Git history for credentials,
  tokens, private keys, cookies, email addresses, local paths, usernames,
  customer/user data, internal URLs, and private repository coordinates.
- [ ] Audit large/binary objects and prior versions for private design documents,
  visual-reference photographs, VM images, ISO material, captures, generated
  caches, and other ignored-but-historically-tracked files.
- [ ] Scan the exact source archive, wheel/bundle, native artifact, browser artifact,
  source maps, metadata, and SBOM—not just Git—for the same material.
- [ ] Review commit messages, author/committer identity, signed tags, and trailers
  for sensitive references or identities that should not be public.
- [ ] Inventory dependencies and bundled binaries; record licenses and known
  vulnerabilities appropriate to the supported versions.
- [ ] If history is rewritten, rotate every exposed credential first, coordinate
  all private clones, invalidate old release artifacts, and rerun the entire
  audit on the new canonical refs.
- [ ] A second reviewer examines the scan configuration and manually samples the
  history and artifacts; a scanner’s zero-result output alone is insufficient.
- [ ] A sanitized audit record captures tools, versions, patterns/categories,
  refs, commit, date, findings, remediation, false-positive rationale, and final
  reviewer sign-off without reproducing secrets.

**Required evidence:** sanitized audit report, ref inventory, binary/history
inventory, dependency/SBOM report, remediation record, exact-candidate rescan,
and second-reviewer sign-off.

## G8 — Public positioning, roadmap, screenshots, and trailer (MUST)

The presentation should show the game at its strongest while remaining exact
about alpha boundaries.

- [ ] A curated screenshot set covers the install flow, Ultra traversal,
  vertical procedural play, item/action HUD, RPG conversion battle, signature
  edit event, and one lower-fidelity/CRT example.
- [ ] Screenshots come from the tagged release artifact, contain no debug UI or
  private data, and use readable framing without misrepresenting gameplay.
- [ ] A short gameplay trailer shows continuous or honestly edited footage from
  the release artifact, including player input and the Chapter 1 loop. It does
  not imply that later chapters or full-campaign web content ship in 0.2.
- [ ] The public README leads with how to play, what is complete, how to
  contribute, project leadership, Limitless’s optional role, rights/disclaimer,
  and the security-reporting route.
- [x] `ROADMAP.md` is small and directional:
  - **0.2:** polished Chapter 1, content packs, real Limitless exchange, public
    contribution infrastructure;
  - **0.2.x:** accessibility, performance, tooling, pack ecosystem, and Chapter 1
    refinement;
  - **0.3+:** later chapters and broader platform work only as they become
    production-ready.
- [ ] The release invites targeted contributions to art, audio, accessibility,
  level content, enemies, methods, and content packs while reserving canon and
  final product decisions to maintainers.
- [ ] Release notes include known limitations: Chapter 1 web scope and browser
  qualification, any unqualified Omarchy-shell surface, and later-chapter scaffolding.

**Required evidence:** final media files, capture provenance, public README and
roadmap, release draft, known-limitations review, and founder approval.

## G9 — Exact-candidate rehearsal and public cutover (MUST)

- [ ] Freeze an exact release-candidate commit after G0–G8 are believed complete.
- [ ] Build and test from a fresh clone at that commit; no working-tree artifact
  may be substituted.
- [ ] Run the complete automated suite, content-pack validation, package build,
  clean artifact install, Chapter 1 playthrough, Limitless exchange, rights scan,
  and sensitive-history scan against the frozen candidate.
- [ ] Reconcile README, release notes, and in-game claims with the candidate.
  No known contradiction remains.
- [ ] Confirm all G0–G9 checklist items and global invariants are **PASS** and link
  them to a single cutover evidence index.
- [ ] Prepare the `0.2.0` tag, checksums, artifacts, release notes, screenshots,
  trailer, issue labels/forms, branch protection, and security contact before
  changing visibility.
- [ ] Verify public artifacts contain no release credential and untrusted CI
  cannot publish or mutate protected refs.
- [ ] Obtain separate founder authorization naming the exact commit and planned
  visibility-change time.
- [ ] Change repository visibility manually, verify the anonymous public view,
  publish the prepared release, and rerun public install links.
- [ ] Record post-cutover rollback/incident contacts. Repository visibility is
  not treated as a reversible substitute for completing the gates.

**Required evidence:** cutover evidence index, exact commit/tag, green clean-clone
run, artifact hashes, anonymous-view check, founder authorization, and final
post-cutover smoke test.

## Explicit non-gates for 0.2

The following work may be valuable, but it must not delay the open-development
cutover when G0–G9 pass:

- completion or end-to-end qualification of Chapters 2–6;
- full-campaign feature parity and broad browser/mobile qualification;
- synchronous multiplayer;
- photo-based character import;
- a Godot migration;
- every planned enemy, boss, item, method, biome, or content pack;
- a broad public governance council or community vote over canon.

These are not permission to overclaim. Unfinished features remain hidden,
disabled, or plainly labelled.

## Maintainer-led contribution model

The project accepts help without outsourcing its identity.

Maintainers publish bounded opportunities, schemas, art direction, acceptance
criteria, and roadmap priorities. Contributors may propose and implement
improvements, especially in art, audio, accessibility, levels, enemies,
methods, tests, tooling, and content packs. Maintainers retain final decisions
over story, satire, voice, canon, architecture, safety, releases, and what joins
the built-in game.

A good external contribution should be independently useful, reviewable, and
reversible. Content packs are the preferred surface for experimental content;
merging an external pack into canon is a separate maintainer decision.

## Cutover sign-off

Complete this table only against a frozen release candidate.

| Gate | Status | Evidence | Reviewer | Date |
|---|---|---|---|---|
| Global invariants |  |  |  |  |
| G0 — Scope and authority |  |  |  |  |
| G1 — Chapter 1 |  |  |  |  |
| G2 — Install/artifact |  |  |  |  |
| G3 — CI/contribution |  |  |  |  |
| G4 — Content packs |  |  |  |  |
| G5 — Rights |  |  |  |  |
| G6 — Limitless exchange |  |  |  |  |
| G7 — Sensitive audit |  |  |  |  |
| G8 — Positioning/media |  |  |  |  |
| G9 — Rehearsal/cutover |  |  |  |  |

Final founder authorization:

- Release commit/tag:
- Authorization date/time:
- Authorized by:
- Repository visibility change performed by:
- Public artifact smoke test:
