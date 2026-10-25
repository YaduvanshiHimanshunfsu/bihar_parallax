"""Parallax API package."""

from pathlib import Path
import sys

# The forensic engine is deliberately outside the HTTP application so it can be
# evaluated independently. This keeps local `uvicorn app.main:app` development
# simple until the project is packaged as an installable workspace.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
