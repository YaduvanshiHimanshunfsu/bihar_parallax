from __future__ import annotations

import wave

import numpy as np

from forensic_engine.audio.analysis import analyse_audio


def make_wav(path) -> None:
    sample_rate = 8_000
    silence = np.zeros(sample_rate * 2, dtype=np.int16)
    time = np.arange(sample_rate * 2) / sample_rate
    tone = (0.45 * np.sin(2 * np.pi * 440 * time) * np.iinfo(np.int16).max).astype(np.int16)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(np.concatenate([silence, tone]).tobytes())


def test_audio_analysis_returns_explainable_wav_review_and_visual_artifact(tmp_path) -> None:
    sample = tmp_path / "recording.wav"
    make_wav(sample)

    result = analyse_audio(sample)

    assert result.summary["sample_rate_hz"] == 8_000
    assert result.summary["channels"] == 1
    assert result.waveform_png is not None
    assert result.waveform_png.startswith(b"\x89PNG\r\n\x1a\n")
    assert "audio.silence.intervals" in {finding.code for finding in result.findings}
    assert "audio.energy.discontinuities" in {finding.code for finding in result.findings}
