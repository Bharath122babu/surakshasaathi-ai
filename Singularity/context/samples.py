"""
context/samples.py
──────────────────
Backward-compatible shim — imports SCAM_DATA from data.py and exposes
SCAM_SAMPLES so all existing code (matcher, engine, app) keeps working.

To add new scam patterns, edit context/data.py only.
"""

from context.data import SCAM_DATA

# Alias used throughout the rest of the codebase
SCAM_SAMPLES = SCAM_DATA
