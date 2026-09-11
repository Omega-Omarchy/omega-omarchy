"""Omega Omarchy — the revolution will be customized."""

from __future__ import annotations

__version__ = "0.1.0"
GENERATOR_VERSION = "3.12.0"
SCHEMA_VERSION = "1.0.0"
COMPATIBILITY_TARGET = "omega-omarchy/linux-web/1"
FIXTURE_SEED = "omega-fixture-1"
INSTALLER_COMPLETION_ACTION = "Play Now"

from .campaign import CAMPAIGN_ROSTER, campaign_roster_names
from .identity import WorldIdentity, canonical_json_bytes, sha256_json
from .installer import InstallerSession

__all__ = [
    "CAMPAIGN_ROSTER",
    "COMPATIBILITY_TARGET",
    "FIXTURE_SEED",
    "GENERATOR_VERSION",
    "INSTALLER_COMPLETION_ACTION",
    "SCHEMA_VERSION",
    "InstallerSession",
    "WorldIdentity",
    "campaign_roster_names",
    "canonical_json_bytes",
    "sha256_json",
    "__version__",
]
