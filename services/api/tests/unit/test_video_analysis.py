from __future__ import annotations

import cv2
import numpy as np

from forensic_engine.video.analysis import analyse_video


def make_avi(path) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 5.0, (64, 48))
    assert writer.isOpened(), "The OpenCV test fixture could not create an AVI file."
    try:
        for index in range(12):
            value = 20 if index < 6 else 230
            frame = np.full((48, 64, 3), value, dtype=np.uint8)
            writer.write(frame)
    finally:
        writer.release()


def test_video_analysis_returns_bounded_sequence_review_and_contact_sheet(tmp_path) -> None:
    sample = tmp_path / "sequence.avi"
    make_avi(sample)

    result = analyse_video(sample, max_samples=12)

    assert result.summary["reported_frame_count"] >= 12
    assert result.summary["decoded_sample_count"] >= 2
    assert result.contact_sheet_png is not None
    assert result.contact_sheet_png.startswith(b"\x89PNG\r\n\x1a\n")
    assert "video.frame.duplicate_candidates" in {finding.code for finding in result.findings}
    assert "video.frame.transition_outliers" in {finding.code for finding in result.findings}
