from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image, ImageChops, ImageEnhance, ImageStat, UnidentifiedImageError


@dataclass(frozen=True)
class ForensicFinding:
    code: str
    severity: str
    title: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImageAnalysisResult:
    image_format: str
    width: int
    height: int
    color_mode: str
    metadata: dict[str, Any]
    findings: list[ForensicFinding]
    ela_png: bytes | None
    ela_metrics: dict[str, float] | None


_EXIF_FIELDS = {
    271: "make",
    272: "model",
    305: "software",
    306: "modified_at",
    36867: "captured_at",
    36868: "digitized_at",
}
_DATETIME_FORMAT = "%Y:%m:%d %H:%M:%S"
_EDITING_SOFTWARE = ("adobe", "photoshop", "gimp", "lightroom", "canva", "snapseed", "picsart")


def _normalise_exif_value(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip("\x00")
    return str(value).strip("\x00")


def _extract_metadata(image: Image.Image) -> dict[str, Any]:
    exif = image.getexif()
    metadata: dict[str, Any] = {
        "has_exif": bool(exif),
        "has_gps": False,
        "fields": {},
    }
    for tag_id, field_name in _EXIF_FIELDS.items():
        value = exif.get(tag_id)
        if value not in (None, ""):
            metadata["fields"][field_name] = _normalise_exif_value(value)

    try:
        gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
        metadata["has_gps"] = bool(gps_ifd)
    except (KeyError, AttributeError, TypeError):
        metadata["has_gps"] = False
    return metadata


def _timestamp_findings(metadata: dict[str, Any]) -> list[ForensicFinding]:
    fields = metadata["fields"]
    timestamps: dict[str, datetime] = {}
    for key in ("captured_at", "digitized_at", "modified_at"):
        raw = fields.get(key)
        if not raw:
            continue
        try:
            timestamps[key] = datetime.strptime(raw, _DATETIME_FORMAT)
        except ValueError:
            continue

    findings: list[ForensicFinding] = []
    if len(timestamps) < 2:
        findings.append(
            ForensicFinding(
                code="metadata.timestamp.limited",
                severity="info",
                title="Limited embedded timestamp data",
                detail="Fewer than two parseable embedded timestamps were available for comparison. This is common after sharing or export and is not evidence of tampering.",
                evidence={"available_fields": sorted(timestamps)},
            )
        )
        return findings

    earliest = min(timestamps.values())
    latest = max(timestamps.values())
    difference_hours = round(abs((latest - earliest).total_seconds()) / 3600, 2)
    if difference_hours >= 24:
        findings.append(
            ForensicFinding(
                code="metadata.timestamp.conflict",
                severity="review",
                title="Embedded timestamps differ materially",
                detail="Embedded image timestamps differ by at least 24 hours. Device clocks, exports, and editing workflows can cause this; compare it with case context before drawing a conclusion.",
                evidence={"timestamps": {key: value.isoformat() for key, value in timestamps.items()}, "difference_hours": difference_hours},
            )
        )
    else:
        findings.append(
            ForensicFinding(
                code="metadata.timestamp.consistent",
                severity="info",
                title="Available embedded timestamps are broadly consistent",
                detail="The available embedded timestamps are within 24 hours of one another. This does not prove the image is authentic.",
                evidence={"timestamps": {key: value.isoformat() for key, value in timestamps.items()}, "difference_hours": difference_hours},
            )
        )
    return findings


def _metadata_findings(metadata: dict[str, Any]) -> list[ForensicFinding]:
    fields = metadata["fields"]
    findings = _timestamp_findings(metadata)
    software = fields.get("software", "")
    if software:
        severity = "review" if any(name in software.lower() for name in _EDITING_SOFTWARE) else "info"
        findings.append(
            ForensicFinding(
                code="metadata.software.present",
                severity=severity,
                title="Software tag present",
                detail="The metadata records software associated with the file. A software tag can result from normal camera, export, or editing workflows and is not proof of alteration.",
                evidence={"software": software},
            )
        )
    if not metadata["has_exif"]:
        findings.append(
            ForensicFinding(
                code="metadata.exif.absent",
                severity="info",
                title="No EXIF block found",
                detail="No EXIF block was found. Messaging platforms and export tools often remove metadata, so absence alone is not suspicious.",
                evidence={},
            )
        )
    return findings


def _ela(image: Image.Image) -> tuple[bytes, dict[str, float], ForensicFinding]:
    rgb = image.convert("RGB")
    recompressed_buffer = io.BytesIO()
    rgb.save(recompressed_buffer, "JPEG", quality=90, optimize=True)
    recompressed_buffer.seek(0)
    with Image.open(recompressed_buffer) as recompressed:
        difference = ImageChops.difference(rgb, recompressed.convert("RGB"))
    extrema = difference.getextrema()
    maximum = max(channel[1] for channel in extrema)
    mean_channel_difference = sum(ImageStat.Stat(difference).mean) / 3
    enhancement = 1.0 if maximum == 0 else min(64.0, 255.0 / maximum)
    heatmap = ImageEnhance.Brightness(difference).enhance(enhancement)
    output = io.BytesIO()
    heatmap.save(output, "PNG", optimize=True)

    metrics = {
        "maximum_channel_difference": float(maximum),
        "mean_channel_difference": round(float(mean_channel_difference), 4),
        "brightness_scale": round(float(enhancement), 2),
        "recompression_quality": 90.0,
    }
    title = "JPEG recompression difference map generated"
    detail = "The heatmap visualises pixel differences after controlled JPEG recompression. Bright regions are review leads only; ELA can react to ordinary recompression, resizing, and export history."
    if maximum >= 32 and mean_channel_difference >= 2.0:
        severity = "review"
        detail += " The image contains locally stronger recompression differences, so compare highlighted regions with the original scene and metadata."
    else:
        severity = "info"
    finding = ForensicFinding(
        code="image.ela.generated",
        severity=severity,
        title=title,
        detail=detail,
        evidence=metrics,
    )
    return output.getvalue(), metrics, finding


def analyse_image(path: Path) -> ImageAnalysisResult:
    """Analyse image facts, EXIF consistency, and JPEG ELA without mutating input."""
    try:
        with Image.open(path) as source:
            source.load()
            image_format = (source.format or "unknown").upper()
            width, height = source.size
            color_mode = source.mode
            metadata = _extract_metadata(source)
            findings = _metadata_findings(metadata)
            if image_format == "JPEG":
                ela_png, ela_metrics, ela_finding = _ela(source)
                findings.append(ela_finding)
            else:
                ela_png = None
                ela_metrics = None
                findings.append(
                    ForensicFinding(
                        code="image.ela.not_applicable",
                        severity="info",
                        title="JPEG ELA not applicable",
                        detail="Error Level Analysis is specific to JPEG recompression. This file is not a JPEG, so no ELA heatmap was produced.",
                        evidence={"image_format": image_format},
                    )
                )
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("The submitted evidence could not be decoded as a supported image.") from exc

    return ImageAnalysisResult(
        image_format=image_format,
        width=width,
        height=height,
        color_mode=color_mode,
        metadata=metadata,
        findings=findings,
        ela_png=ela_png,
        ela_metrics=ela_metrics,
    )
