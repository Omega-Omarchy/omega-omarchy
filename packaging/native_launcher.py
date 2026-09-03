"""Small frozen entry point; package-relative __main__ cannot run as a file."""

from omega_omarchy.cli import main


raise SystemExit(main())
