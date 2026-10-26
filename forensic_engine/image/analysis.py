from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
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


def _copy_move_candidate_finding(image: Image.Image) -> ForensicFinding:
    """Find internally repeated ORB features as a bounded copy-move review lead.

    Repeated visual features are common in bricks, foliage, text and other regular
    scene detail. This deliberately reports *candidate correspondences*, never a
    conclusion that a copied region was pasted into the image.
    """
    grayscale = np.asarray(image.convert("L"))
    height, width = grayscale.shape
    original_dimensions = {"width": int(width), "height": int(height)}
    if min(width, height) < 64:
        return ForensicFinding(
            code="image.copy_move.unavailable",
            severity="info",
            title="Image too small for copy-move feature review",
            detail="The image has insufficient spatial detail for the bounded feature-matching review. This is not an integrity finding.",
            evidence=original_dimensions,
        )

    scale = min(1.0, 1600.0 / max(width, height))
    if scale < 1.0:
        working = cv2.resize(grayscale, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
    else:
        working = grayscale
    detector = cv2.ORB_create(nfeatures=1_200, fastThreshold=12)
    keypoints, descriptors = detector.detectAndCompute(working, None)
    keypoint_count = len(keypoints)
    base_evidence = {
        **original_dimensions,
        "working_scale": round(scale, 4),
        "working_width": int(working.shape[1]),
        "working_height": int(working.shape[0]),
        "keypoint_count": keypoint_count,
        "feature_detector": "ORB",
    }
    if descriptors is None or keypoint_count < 12:
        return ForensicFinding(
            code="image.copy_move.limited",
            severity="info",
            title="Limited local features for copy-move review",
            detail="Too few stable local features were available for internal correspondence screening. Smooth, dark, blurred, or highly compressed images can produce this result.",
            evidence=base_evidence,
        )

    raw_matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(descriptors, descriptors, k=min(5, keypoint_count))
    minimum_separation = max(24.0, min(working.shape) * 0.08)
    distance_limit = 36
    candidate_pairs: list[tuple[float, float, float, float, int]] = []
    seen_pairs: set[tuple[int, int]] = set()
    for nearby in raw_matches:
        if not nearby:
            continue
        query = nearby[0].queryIdx
        for match in nearby[1:]:  # First result is the feature matching itself.
            if match.distance > distance_limit or query == match.trainIdx:
                continue
            pair = tuple(sorted((query, match.trainIdx)))
            if pair in seen_pairs:
                continue
            left = keypoints[query].pt
            right = keypoints[match.trainIdx].pt
            if float(np.hypot(left[0] - right[0], left[1] - right[1])) < minimum_separation:
                continue
            seen_pairs.add(pair)
            candidate_pairs.append((left[0], left[1], right[0], right[1], int(match.distance)))
            break

    base_evidence["descriptor_distance_limit"] = distance_limit
    base_evidence["minimum_spatial_separation_pixels"] = round(minimum_separation, 2)
    base_evidence["candidate_pair_count"] = len(candidate_pairs)
    # A small sample makes an investigator's follow-up reproducible without
    # flooding the report with hundreds of similar keypoint pairs.
    base_evidence["candidate_pairs"] = [
        {
            "first_xy": [round(x1 / scale, 1), round(y1 / scale, 1)],
            "second_xy": [round(x2 / scale, 1), round(y2 / scale, 1)],
            "hamming_distance": distance,
        }
        for x1, y1, x2, y2, distance in candidate_pairs[:20]
    ]
    if len(candidate_pairs) >= 12:
        return ForensicFinding(
            code="image.copy_move.candidates",
            severity="review",
            title="Repeated local-feature correspondences require visual review",
            detail="Spatially separated, visually similar feature pairs were found. Repeating textures and scene structure can produce the same result; inspect the listed coordinates and source context before inferring copy-move editing.",
            evidence=base_evidence,
        )
    return ForensicFinding(
        code="image.copy_move.no_strong_candidates",
        severity="info",
        title="No strong copy-move feature cluster identified",
        detail="The bounded local-feature screen did not find a strong cluster of spatially separated correspondences. It does not rule out manipulation, especially after resizing, blur, recompression, or very small edits.",
        evidence=base_evidence,
    )


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
            findings.append(_copy_move_candidate_finding(source))
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
