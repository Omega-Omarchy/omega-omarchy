# Data-only content packs

Omega Omarchy's first content-pack contract is deliberately narrow and
fail-closed. It externalizes the Chapter 1 generation profile and permits
ordered add-ons to extend its terrain recipes, sector motifs, enemy motifs, and
item pool. It does not execute pack code, scan arbitrary directories, fetch
URLs, or yet accept custom art, dialogue, encounters, enemy definitions, or
items.

The built-in pack at
`src/omega_omarchy/data/content-packs/omega-core/` uses the same loader and
validator as the example at `examples/content-packs/vertical-garden/`.

## Try the maintained example

```bash
./scripts/omega validate-pack examples/content-packs/vertical-garden
./scripts/omega review-pack examples/content-packs/vertical-garden
./scripts/omega install-pack examples/content-packs/vertical-garden --accept
./scripts/omega enable-pack example.vertical-garden
./scripts/omega run
./scripts/omega dump-identity --seed omega-fixture-1
```

`review-pack` is read-only and shows the local source label, declared source and
homepage, exact version and digest, authors, license, requested capabilities,
dependencies, compatibility versions, file count, byte count, and entry count.
`install-pack` validates and repeats that review, and refuses to write without
the explicit `--accept` flag. Installation never activates a pack. Activation
is a separate `enable-pack` action.

Enabled packs apply by default to native play and identity inspection. Use
`--no-installed-content` for a one-off core-only run, or `disable-pack` to make
the change persistent. The original `--content-pack PATH` option remains useful
for a one-off authoring test without installation. Additional packs do not
apply to the explicitly limited Chapter 1 browser alpha; installing or enabling
external packs remains native-only.

Never disable and remove a pack that a retained save needs unless losing access
to that save is intentional: loading fails safely and names the exact missing
pack rather than substituting core content.

## Installed-pack lifecycle

The lifecycle accepts a sealed regular directory or a `.zip` containing exactly
one pack at its root or in one top-level directory:

```bash
# Inspect without writing anything.
./scripts/omega review-pack path/to/example-pack.zip

# Repeats the review and installs disabled into game-owned storage.
./scripts/omega install-pack path/to/example-pack.zip --accept
./scripts/omega list-packs

# Apply it to subsequent native runs, then verify the sealed identity.
./scripts/omega enable-pack example.pack-id
./scripts/omega dump-identity --seed omega-fixture-1

# Stop applying it, then remove only the game-owned installed copy.
./scripts/omega disable-pack example.pack-id
./scripts/omega remove-pack example.pack-id
```

On Linux, storage is
`$XDG_DATA_HOME/omega-omarchy/content-packs/` when `XDG_DATA_HOME` is absolute,
otherwise `~/.local/share/omega-omarchy/content-packs/`. The registry binds each
ID, version, digest, and relative path with its own digest and is written
atomically under a process lock. Installed copies are validated again at list,
activation, and launch. A corrupt registry, missing pack, changed payload,
dependency failure, conflict, or ordering cycle stops activation. The game
never silently repairs, upgrades, or substitutes content.

Multiple versions may be installed, but only one version of an ID may be
enabled. If a command is ambiguous, select it with `--pack-version x.y.z`. The
same ID and version cannot be replaced with a different digest. Removal is
blocked until that exact installation is disabled.

## Directory and manifest

Every current pack is a regular directory containing `pack.toml`, `LICENSE`,
`ATTRIBUTION.md`, and one or more declared JSON entry points. All other files
must also be declared. Symlinks are forbidden.

```toml
id = "example.vertical-garden"
version = "1.0.0"
schemaVersion = "1.0.0"
gameSchemaVersion = "1.0.0"
generatorVersion = "3.8.0"
license = "CC0-1.0"
authors = ["Omega Omarchy contributors"]
entryPoints = ["chapters/vertical-garden-addon.json"]
dependencies = ["omega-core-1"]
loadAfter = ["omega-core-1"]
loadBefore = []
loadOrder = 100
capabilities = ["chapter-profile"]
contentDigest = "sha256:..."

[[files]]
path = "chapters/vertical-garden-addon.json"
digest = "sha256:..."
bytes = 281
mediaType = "application/json"
```

Optional `homepage` and `source` fields are descriptive text only. The game
does not access either address. Dependencies and order constraints currently
name exact pack IDs. Topological constraints win; otherwise `loadOrder`, pack
ID, and version provide deterministic ordering. Duplicate pack IDs, duplicate
entry IDs, missing constraints, and cycles are errors.

`contentDigest` binds the supported manifest metadata and the sorted path,
size, media type, and digest of every file. World identity binds the ordered
pack IDs and an aggregate content digest; the receipt additionally records
each exact pack version and digest.

## Entry reference

Schema `1.0.0` accepts two JSON object kinds:

- `chapter` defines one base profile with `id`, `chapterId`, `name`, `blurb`,
  `palette`, `boss`, `generation`, and optional `enemyMotifs`/`itemPool`.
- `chapter-addon` names an existing `chapterId` and may append supported
  `generation.recipes`, `generation.sectorMotifs`, `enemyMotifs`, and
  `itemPool` values.

A base `generation` defines `widthBase` values for `casual`, `standard`, and
`precise`, plus `heightBase`, `sectorWidth`, non-empty `sectorMotifs`, and
non-empty `recipes`. Add-ons may provide a subset. Identifiers and recipes must
already be supported by the engine; unsupported fields and capabilities are
rejected rather than ignored. See the built-in and example JSON files for the
smallest authoritative examples.

## Authoring workflow

1. Copy `examples/content-packs/vertical-garden/` to a new working directory.
2. Change its globally unique lowercase `id`, version, author, license, and
   attribution. Change the JSON entry ID as well.
3. Edit only the declarative JSON fields described above.
4. Refresh every file declaration and digest atomically:

   ```bash
   ./scripts/omega seal-pack path/to/your-pack
   ```

5. Validate without activating it:

   ```bash
   ./scripts/omega validate-pack path/to/your-pack
   ```

   The success line shows the pack ID, version, digest, license, capabilities,
   local source path, and entry count.

6. Exercise the player lifecycle with `review-pack`, `install-pack --accept`,
   `list-packs`, and `enable-pack`. Repeat the same seed with enabled content and
   `--no-installed-content`; `dump-identity` must report different sealed world
   identities.
7. Run `disable-pack`, then `remove-pack`. Do not edit or delete files inside
   game-owned storage by hand.

`seal-pack` validates a private staging copy before replacing `pack.toml`; an
invalid schema or unsafe payload leaves the source manifest unchanged.

## Safety limits

Validation happens before activation and rejects absolute/traversal/backslash
paths, symlinks, undeclared or missing files, executable extensions and fields,
non-finite or duplicate-key JSON, unsupported features, malformed identifiers,
digest/size mismatches, incompatible schema/generator versions, unsupported
chapter targets, and excessive file, pack, JSON-node, or nesting sizes. Current
ceilings are 256 files, 4 MiB per file,
24 MiB per pack, 20,000 JSON nodes, and 16 levels of JSON nesting.

ZIP review additionally rejects encryption, links and special files, duplicate
portable names, multiple manifests, ambiguous roots, files outside the pack
root, excessive compressed/expanded sizes, and excessive member counts. ZIP
contents are copied to private staging and passed through the directory
validator; the archive is never extracted directly into the installed store.

Packs cannot write game data merely by being reviewed, validated, or activated.
`seal-pack` only rewrites `pack.toml` inside the exact author directory supplied;
`install-pack --accept` only writes a validated copy and registry record below
the game-owned data directory.

## Compatibility and migration policy

The three compatibility fields are independent:

- `schemaVersion` identifies this pack format.
- `gameSchemaVersion` identifies the sealed world/save schema.
- `generatorVersion` identifies deterministic map generation.

This private-alpha loader requires exact matches and rejects incompatibility;
it never guesses or silently upgrades content. A breaking field, meaning, merge
rule, or canonicalization change requires a new pack schema version. Before a
public 0.2 freeze, the project must either ship a deterministic migration tool
that produces a newly sealed pack or document a clear rejection and manual
migration. New optional fields may be added only when older loaders already
reject them safely and the compatibility table is updated.

The current boundary is evidence toward cutover gate G4, not completion of it.
External custom definitions/assets, an in-game graphical review UI, semver
compatibility ranges, and migration of later-chapter scaffolding remain open.
