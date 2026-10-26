from __future__ import annotations

import io

from PIL import Image, ImageDraw

from forensic_engine.image.analysis import analyse_image


def make_jpeg(path) -> None:
    image = Image.new("RGB", (96, 72), "#32516a")
    draw = ImageDraw.Draw(image)
    draw.rectangle((51, 14, 85, 48), fill="#f1cb52")
    exif = Image.Exif()
    exif[305] = "Adobe Photoshop"
    exif[306] = "2026:10:25 13:00:00"
    exif[36867] = "2026:10:01 11:30:00"
    image.save(path, format="JPEG", quality=95, exif=exif)


def test_jpeg_analysis_returns_explainable_metadata_and_ela(tmp_path) -> None:
    sample = tmp_path / "sample.jpg"
    make_jpeg(sample)

    result = analyse_image(sample)

    assert result.image_format == "JPEG"
    assert result.width == 96
    assert result.ela_png is not None
    assert result.ela_png.startswith(b"\x89PNG\r\n\x1a\n")
    codes = {finding.code for finding in result.findings}
    assert "metadata.timestamp.conflict" in codes
    assert "metadata.software.present" in codes
    assert "image.ela.generated" in codes
    assert any(code.startswith("image.copy_move.") for code in codes)


def test_png_analysis_never_claims_ela_support(tmp_path) -> None:
    sample = tmp_path / "sample.png"
    Image.new("RGB", (48, 48), "#173448").save(sample, format="PNG")

    result = analyse_image(sample)

    assert result.ela_png is None
    assert "image.ela.not_applicable" in {finding.code for finding in result.findings}
    assert any(finding.code.startswith("image.copy_move.") for finding in result.findings)
