from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_ui_shell_and_live_contract_assets_are_served(settings: Settings) -> None:
    project_root = Path(__file__).resolve().parents[4]
    application = create_app(replace(settings, web_dir=project_root / "apps" / "web"))
    client = TestClient(application)

    home = client.get("/")
    workbench = client.get("/stitch-app.js")
    styles = client.get("/stitch.css")
    health = client.get("/api/v1/health")
    version = client.get("/api/v1/version")

    assert home.status_code == 200
    assert 'src="stitch-app.js"' in home.text
    assert workbench.status_code == 200
    assert 'api("/dashboard")' in workbench.text
    assert 'verify-audit' in workbench.text
    assert styles.status_code == 200
    assert "--px-canvas" in styles.text
    assert health.json()["status"] == "ok"
    assert "ORB copy-move candidates" in version.json()["modules"]["image"]
