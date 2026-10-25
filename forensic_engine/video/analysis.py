from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw


@dataclass(frozen=True)
class VideoForensicFinding:
    code: str
    severity: str
    title: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VideoAnalysisResult:
    summary: dict[str, Any]
    findings: list[VideoForensicFinding]
    contact_sheet_png: bytes | None


def _frame_signature(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, (48, 48), interpolation=cv2.INTER_AREA).astype(np.float32)


def _thumbnail(frame: np.ndarray, label: str) -> Image.Image:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(rgb)
    image.thumbnail((260, 150))
    tile = Image.new("RGB", (272, 184), "#0b1220")
    tile.paste(image, ((272 - image.width) // 2, 8))
    ImageDraw.Draw(tile).text((8, 162), label, fill="#d5e4f4")
    return tile


def _contact_sheet(samples: list[tuple[int, np.ndarray]]) -> bytes | None:
    if not samples:
        return None
    selected = samples[:12]
    columns = 3
    rows = math.ceil(len(selected) / columns)
    sheet = Image.new("RGB", (columns * 272, rows * 184), "#050b16")
    for index, (frame_number, frame) in enumerate(selected):
        sheet.paste(_thumbnail(frame, f"sampled frame {frame_number}"), ((index % columns) * 272, (index // columns) * 184))
    output = io.BytesIO()
    sheet.save(output, "PNG", optimize=True)
    return output.getvalue()


def analyse_video(path: Path, max_samples: int = 300) -> VideoAnalysisResult:
    """Create conservative review leads from sampled frames without modifying the original.

    This is deliberately not a claim that a duplicate or discontinuity proves insertion,
    deletion, or reordering. Static scenes, normal cuts, packet loss, and transcoding
    can yield the same signals.
    """
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError("The submitted evidence could not be decoded as a supported video.")
    try:
        reported_frame_count = max(0, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        width = max(0, int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)))
        height = max(0, int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        if reported_frame_count <= 0 or width <= 0 or height <= 0:
            raise ValueError("The video has no decodable frame sequence or dimensions.")

        sample_count = min(max_samples, reported_frame_count)
        indexes = np.linspace(0, reported_frame_count - 1, num=sample_count, dtype=int)
        indexes = np.unique(indexes)
        samples: list[tuple[int, np.ndarray]] = []
        signatures: list[np.ndarray] = []
        for frame_number in indexes.tolist():
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            samples.append((frame_number, frame))
            signatures.append(_frame_signature(frame))
    finally:
        capture.release()

    if len(samples) < 2:
        raise ValueError("Too few video frames could be sampled for sequence review.")

    differences = np.array(
        [float(np.mean(np.abs(current - previous))) for previous, current in zip(signatures, signatures[1:])],
        dtype=float,
    )
    duplicate_threshold = 0.8
    duplicate_indices = np.where(differences <= duplicate_threshold)[0].tolist()
    median_difference = float(np.median(differences))
    median_absolute_deviation = float(np.median(np.abs(differences - median_difference)))
    transition_threshold = max(35.0, median_difference + (5.0 * median_absolute_deviation))
    transition_indices = np.where(differences >= transition_threshold)[0].tolist()

    duration_seconds = round(reported_frame_count / fps, 3) if fps > 0 else None
    summary = {
        "reported_frame_count": reported_frame_count,
        "decoded_sample_count": len(samples),
        "sampling_interval_frames": max(1, round(reported_frame_count / len(samples))),
        "fps": round(fps, 3),
        "duration_seconds": duration_seconds,
        "width": width,
        "height": height,
        "mean_sample_difference": round(float(np.mean(differences)), 4),
        "median_sample_difference": round(median_difference, 4),
        "duplicate_difference_threshold": duplicate_threshold,
        "transition_difference_threshold": round(transition_threshold, 4),
    }
    duplicate_frame_pairs = [
        {"from_frame": samples[index][0], "to_frame": samples[index + 1][0], "difference": round(float(differences[index]), 4)}
        for index in duplicate_indices[:20]
    ]
    transition_frame_pairs = [
        {"from_frame": samples[index][0], "to_frame": samples[index + 1][0], "difference": round(float(differences[index]), 4)}
        for index in transition_indices[:20]
    ]
    findings = [
        VideoForensicFinding(
            code="video.sequence.sampled",
            severity="info",
            title="Video sequence sampled for review",
            detail="Frames were sampled across the decodable timeline. This fast triage pass does not inspect every frame and cannot establish whether frames were inserted, removed, or reordered.",
            evidence=summary,
        ),
        VideoForensicFinding(
            code="video.frame.duplicate_candidates",
            severity="review" if duplicate_frame_pairs else "info",
            title="Potential near-duplicate sampled frames" if duplicate_frame_pairs else "No near-duplicate sampled frame pairs",
            detail=(
                "Very similar sampled frames were found. Static CCTV scenes, low frame rate, freezing, or transcoding can cause this; inspect the original sequence before treating it as a continuity issue."
                if duplicate_frame_pairs
                else "No adjacent sampled pairs met the near-duplicate threshold. This is not proof that the sequence is complete."
            ),
            evidence={"candidate_pairs": duplicate_frame_pairs, "candidate_count": len(duplicate_indices), "threshold": duplicate_threshold},
        ),
        VideoForensicFinding(
            code="video.frame.transition_outliers",
            severity="review" if transition_frame_pairs else "info",
            title="Abrupt sampled-frame transitions require context" if transition_frame_pairs else "No extreme sampled-frame transitions",
            detail=(
                "Large changes between sampled frames were found. Camera movement, normal cuts, lighting shifts, or encoder behaviour can produce these signals, so validate them against nearby original frames."
                if transition_frame_pairs
                else "No sampled transition exceeded the adaptive review threshold. This does not rule out tampering between samples."
            ),
            evidence={"candidate_pairs": transition_frame_pairs, "candidate_count": len(transition_indices), "threshold": round(transition_threshold, 4)},
        ),
    ]
    return VideoAnalysisResult(summary=summary, findings=findings, contact_sheet_png=_contact_sheet(samples))
