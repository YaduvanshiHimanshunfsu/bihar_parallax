from __future__ import annotations

from pathlib import Path

def test_ui_shell_references_the_dynamic_workbench_assets() -> None:
    project_root = Path(__file__).resolve().parents[4]
    web_dir = project_root / "apps" / "web"

    home = (web_dir / "index.html").read_text(encoding="utf-8")
    workbench = (web_dir / "stitch-app.js").read_text(encoding="utf-8")
    styles = (web_dir / "stitch.css").read_text(encoding="utf-8")

    assert 'src="stitch-app.js"' in home
    assert 'href="stitch.css"' in home
    assert 'api("/dashboard")' in workbench
    assert 'verify-audit' in workbench
    assert "--px-canvas" in styles
