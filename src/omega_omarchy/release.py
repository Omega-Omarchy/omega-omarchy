"""Human-readable build identity for loaders and the installer."""

from __future__ import annotations

import subprocess
from pathlib import Path

from . import __version__

ROOT = Path(__file__).resolve().parents[2]


def revision() -> str:
    try:
        from . import _build_revision

        value = str(getattr(_build_revision, "REVISION", "")).strip()
        if value:
            return value
    except ImportError:
        pass
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def release_label() -> str:
    rev = revision()
    return f"{__version__} · {rev}" if rev else __version__
