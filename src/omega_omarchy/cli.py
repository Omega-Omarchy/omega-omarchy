"""One entry point: build, test, run, dump identity, inspect, web."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from . import FIXTURE_SEED, INSTALLER_COMPLETION_ACTION, __version__
from .assets import build_assets, asset_dir
from .campaign import campaign_roster_names
from .content import BUILTIN_PACK, load_content
from .content_pack import PackValidationError, seal_pack, validate_pack
from .generation import generate_world
from .installer import default_fixture_world, InstallerSession
from .omarchy_adapter import load_omarchy_theme
from .pack_store import PackReview, PackStore
from .web_build import build_web

ROOT = Path(__file__).resolve().parents[2]


def _print_identity(seed: str = FIXTURE_SEED, content_paths: tuple[Path, ...] = ()) -> str:
    world = generate_world(seed, force_logo=True, content=load_content(content_paths))
    digest = world.identity.digest()
    print(f"WORLD_IDENTITY={digest}")
    print(f"SEED={world.identity.seed}")
    print(f"GENERATOR={world.identity.generator_version}")
    print(f"SCHEMA={world.identity.schema_version}")
    print(f"CONTENT={world.identity.content_digest}")
    print(f"COMPLETION={INSTALLER_COMPLETION_ACTION}")
    return digest


def _print_campaign() -> None:
    print("CAMPAIGN:" + ",".join(campaign_roster_names()))


def _safe_display(value: str, limit: int = 240) -> str:
    clean = "".join(character if character.isprintable() else " " for character in value)
    return clean[:limit]


def _pack_error_detail(error: PackValidationError | OSError) -> str:
    if isinstance(error, OSError):
        return _safe_display(error.strerror or type(error).__name__)
    return _safe_display(str(error), 500)


def _print_pack_review(review: PackReview) -> None:
    print("PACK_REVIEW")
    print(f"id={review.pack_id}")
    print(f"version={review.version}")
    print(f"digest={review.content_digest}")
    print(f"license={_safe_display(review.license)}")
    print(f"authors={_safe_display(','.join(review.authors))}")
    print(f"capabilities={','.join(review.capabilities)}")
    print(f"dependencies={','.join(review.dependencies) or '-'}")
    print(f"source-file={review.source_label}")
    print(f"declared-source={_safe_display(review.declared_source or '-')}")
    print(f"homepage={_safe_display(review.homepage or '-')}")
    print(
        f"schema={review.schema_version} game-schema={review.game_schema_version} "
        f"generator={review.generator_version} files={review.files} bytes={review.bytes} entries={review.entries}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omega-omarchy", description="Omega Omarchy")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        help=(
            "run|check|test|assets|web|dump-identity|dump-campaign|inspect|play-now|"
            "validate-pack|seal-pack|review-pack|install-pack|list-packs|enable-pack|disable-pack|remove-pack"
        ),
    )
    parser.add_argument("target", nargs="?", help="content-pack source or installed pack id")
    parser.add_argument("--seed", default=FIXTURE_SEED)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--skip-installer", action="store_true")
    parser.add_argument(
        "--warp",
        help=(
            "developer warp: "
            "[chapter-id:]start|boss|edit|portal|pit|cow|stage-map|prologue|map-N"
        ),
    )
    parser.add_argument("--inspect-dir", type=Path)
    parser.add_argument("--ticks", type=int, default=0)
    parser.add_argument("--web-out", type=Path, default=ROOT / "dist" / "web")
    parser.add_argument(
        "--content-pack",
        type=Path,
        action="append",
        default=[],
        help="enable an additional data-only content pack",
    )
    parser.add_argument("--pack-version", help="select an installed content-pack version")
    parser.add_argument("--accept", action="store_true", help="accept reviewed metadata for install-pack")
    parser.add_argument(
        "--no-installed-content",
        action="store_true",
        help="run without content packs enabled in game-owned storage",
    )
    args = parser.parse_args(argv)
    commands = {
        "assets",
        "check",
        "disable-pack",
        "dump-campaign",
        "dump-identity",
        "enable-pack",
        "inspect",
        "install-pack",
        "list-packs",
        "play-now",
        "remove-pack",
        "review-pack",
        "run",
        "seal-pack",
        "test",
        "theme",
        "validate-pack",
        "version",
        "web",
    }
    if args.command not in commands:
        parser.error(f"unknown command: {args.command}")
    targeted_commands = {
        "validate-pack",
        "seal-pack",
        "review-pack",
        "install-pack",
        "enable-pack",
        "disable-pack",
        "remove-pack",
    }
    if args.target and args.command not in targeted_commands:
        parser.error(f"unexpected target for {args.command}: {args.target}")
    if getattr(sys, "frozen", False) and args.command in {"assets", "check", "test", "web"}:
        print(f"UNAVAILABLE_IN_PLAYER_BUNDLE command={args.command}", file=sys.stderr)
        return 2

    store = PackStore()
    if args.command in {"review-pack", "install-pack"}:
        if not args.target:
            parser.error(f"{args.command} requires a pack directory or ZIP archive")
        try:
            review = store.review(Path(args.target))
            _print_pack_review(review)
            if args.command == "review-pack":
                return 0
            if not args.accept:
                print(
                    "PACK_CONFIRM_REQUIRED review the metadata above, then repeat install-pack with --accept",
                    file=sys.stderr,
                )
                return 2
            installed = store.install(
                Path(args.target), accept=True, accepted_digest=review.content_digest
            )
        except (PackValidationError, OSError) as exc:
            print(f"PACK_INVALID {_pack_error_detail(exc)}", file=sys.stderr)
            return 2
        print(
            f"PACK_INSTALLED id={installed.pack_id} version={installed.version} "
            f"digest={installed.content_digest} enabled={'yes' if installed.enabled else 'no'}"
        )
        return 0
    if args.command == "list-packs":
        try:
            installed_packs = store.list()
        except (PackValidationError, OSError) as exc:
            print(f"PACK_INVALID {_pack_error_detail(exc)}", file=sys.stderr)
            return 2
        if not installed_packs:
            print("PACKS_EMPTY")
        for installed in installed_packs:
            print(
                f"PACK id={installed.pack_id} version={installed.version} "
                f"digest={installed.content_digest} enabled={'yes' if installed.enabled else 'no'} "
                f"source={installed.source_label}"
            )
        return 0
    if args.command in {"enable-pack", "disable-pack", "remove-pack"}:
        if not args.target:
            parser.error(f"{args.command} requires an installed pack id")
        try:
            if args.command == "enable-pack":
                installed = store.enable(args.target, args.pack_version)
                action = "ENABLED"
            elif args.command == "disable-pack":
                installed = store.disable(args.target, args.pack_version)
                action = "DISABLED"
            else:
                installed = store.remove(args.target, args.pack_version)
                action = "REMOVED"
        except (PackValidationError, OSError) as exc:
            print(f"PACK_INVALID {_pack_error_detail(exc)}", file=sys.stderr)
            return 2
        print(
            f"PACK_{action} id={installed.pack_id} version={installed.version} "
            f"digest={installed.content_digest}"
        )
        return 0

    content_paths = tuple(args.content_pack)
    if args.command in {"dump-identity", "inspect", "play-now", "run"} and not args.no_installed_content:
        try:
            content_paths = (*store.enabled_paths(), *content_paths)
        except (PackValidationError, OSError) as exc:
            print(f"PACK_INVALID {_pack_error_detail(exc)}", file=sys.stderr)
            return 2
    if args.command in {"check", "dump-identity", "inspect", "play-now", "run"}:
        try:
            load_content(content_paths)
        except (PackValidationError, OSError) as exc:
            print(f"PACK_INVALID {_pack_error_detail(exc)}", file=sys.stderr)
            return 2

    if args.command in {"version", "--version"}:
        print(__version__)
        return 0
    if args.command == "assets":
        path = build_assets(asset_dir())
        print(f"assets={path}")
        return 0
    if args.command == "dump-identity":
        _print_identity(args.seed, content_paths)
        return 0
    if args.command == "dump-campaign":
        _print_campaign()
        print(f"COMPLETION={INSTALLER_COMPLETION_ACTION}")
        return 0
    if args.command == "play-now":
        world = InstallerSession(content_paths=content_paths)
        world.set_choice(seed=args.seed)
        sealed = world.play_now()
        print(INSTALLER_COMPLETION_ACTION)
        print(f"WORLD_IDENTITY={sealed.identity.digest()}")
        return 0
    if args.command == "web":
        if content_paths:
            print("PACK_INVALID the web preview does not support additional content packs", file=sys.stderr)
            return 2
        dest = build_web(args.web_out, seed=args.seed)
        print(f"web={dest}")
        return 0
    if args.command == "validate-pack":
        if not args.target:
            parser.error("validate-pack requires a pack directory")
        try:
            pack = validate_pack(Path(args.target))
        except PackValidationError as exc:
            print(f"PACK_INVALID {exc}", file=sys.stderr)
            return 2
        print(
            f"PACK_OK id={pack.pack_id} version={pack.version} "
            f"digest={pack.content_digest} license={pack.license} "
            f"capabilities={','.join(pack.capabilities)} source={pack.root} entries={len(pack.entries)}"
        )
        return 0
    if args.command == "seal-pack":
        if not args.target:
            parser.error("seal-pack requires a pack directory")
        try:
            pack = seal_pack(Path(args.target))
        except PackValidationError as exc:
            print(f"PACK_INVALID {exc}", file=sys.stderr)
            return 2
        print(f"PACK_SEALED id={pack.pack_id} digest={pack.content_digest}")
        return 0
    if args.command == "test":
        return subprocess.call([sys.executable, "-m", "pytest", str(ROOT / "tests")])
    if args.command == "check":
        validate_pack(BUILTIN_PACK)
        validate_pack(ROOT / "examples" / "content-packs" / "vertical-garden")
        build_assets(asset_dir())
        code = subprocess.call([sys.executable, "-m", "pytest", str(ROOT / "tests")])
        if code != 0:
            return code
        _print_identity(args.seed, content_paths)
        _print_campaign()
        from .app import run_game

        run_game(
            seed=args.seed,
            headless=True,
            dump_identity=True,
            dump_campaign=True,
            skip_installer=False,
            ticks=2,
            content_packs=content_paths,
            dev_warp=args.warp,
        )
        build_web(args.web_out, seed=args.seed)
        print("CHECK_OK")
        return 0
    if args.command == "inspect":
        from .app import run_game

        dest = args.inspect_dir or Path("dist/inspect")
        run_game(
            seed=args.seed,
            headless=True,
            inspect_dir=dest,
            skip_installer=True,
            ticks=1,
            content_packs=content_paths,
            dev_warp=args.warp,
        )
        print(f"inspect={dest}")
        return 0
    if args.command == "theme":
        theme = load_omarchy_theme()
        print("THEME_BG=" + theme.get("background", ""))
        return 0
    # run
    from .app import run_game

    headless = args.headless or not os.environ.get("DISPLAY")
    run_game(
        seed=args.seed,
        headless=headless,
        dump_identity=True,
        dump_campaign=True,
        inspect_dir=args.inspect_dir,
        skip_installer=args.skip_installer,
        ticks=args.ticks,
        content_packs=content_paths,
        dev_warp=args.warp,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
