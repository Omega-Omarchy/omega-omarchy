"""Small frozen entry point; package-relative __main__ cannot run as a file."""

import os

# Keep machine-readable CLI output (especially --version) free of SDL's banner.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from omega_omarchy.cli import main


raise SystemExit(main())
