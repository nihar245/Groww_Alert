"""
config.py — Centralised environment variable loader for Groww Alert.
Reads from a local .env file (development) or from the OS environment
(GitHub Actions / production). Raises clear errors when required vars
are missing so the root cause is obvious.
"""

import os
from pathlib import Path

# Load .env only when the file exists (local dev). In GitHub Actions the
# secrets are injected directly into the environment by the workflow.
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except ImportError:
    pass  # python-dotenv not installed — rely purely on OS env


def _require(var: str) -> str:
    """Return the value of *var* or raise a descriptive RuntimeError."""
    value = os.getenv(var, "").strip()
    if not value:
        raise RuntimeError(
            f"Required environment variable '{var}' is not set.\n"
            f"  • Locally: add it to your .env file (see .env.example).\n"
            f"  • GitHub Actions: add it as a Repository Secret."
        )
    return value


# ── Public constants ──────────────────────────────────────────────────────────

# Recipient WhatsApp number in E.164 format (e.g. +919876543210)
WHATSAPP_PHONE: str = _require("WHATSAPP_PHONE")

# Meta WhatsApp Business Cloud API credentials
# Found at: developers.facebook.com → Your App → WhatsApp → API Setup
WA_PHONE_NUMBER_ID: str = _require("WA_PHONE_NUMBER_ID")
WA_ACCESS_TOKEN: str    = _require("WA_ACCESS_TOKEN")

# Path to the portfolio data file (relative to this script)
PORTFOLIO_PATH: Path = Path(__file__).parent / "portfolio.json"

# AMFI NAV API base URL.
# tracker.py calls  GET {AMFI_API_BASE}/{amfi_code}  (full history, newest-first)
# NOT the /latest endpoint — full history is needed for multi-period P&L.
AMFI_API_BASE: str = "https://api.mfapi.in/mf"
