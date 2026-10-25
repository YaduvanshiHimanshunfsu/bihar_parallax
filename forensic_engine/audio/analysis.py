from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw
from scipy.io import wavfile
from scipy.signal import spectrogram


@dataclass(frozen=True)
class AudioForensicFinding:
    code: str
    severity: str
    title: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AudioAnalysisResult:
    summary: dict[str, Any]
    findings: list[AudioForensicFinding]
    waveform_png: bytes | None


def _normalise(samples: np.ndarray) -> np.ndarray:
    values = samples.astype(np.float32)
    if np.issubdtype(samples.dtype, np.integer):
        values /= max(abs(np.iinfo(samples.dtype).min), np.iinfo(samples.dtype).max)
    return np.clip(values, -1.0, 1.0)


def _find_runs(mask: np.ndarray, minimum_length: int) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, selected in enumerate(mask.tolist() + [False]):
        if selected and start is None:
            start = index
        elif not selected and start is not None:
            if index - start >= minimum_length:
                runs.append((start, index - 1))
            start = None
    return runs


def _render_audio_artifact(signal: np.ndarray, sample_rate: int) -> bytes:
    width, height = 1000, 490
    image = Image.new("RGB", (width, height), "#07111e")
    draw = ImageDraw.Draw(image)
    draw.text((24, 16), "Parallax — derived waveform and spectrogram", fill="#d7e9ff")
    draw.text((24, 40), "Derived visual aid. Preserve and examine the original audio separately.", fill="#87a3c3")
    waveform_top, waveform_bottom = 74, 250
    draw.rectangle((24, waveform_top, width - 24, waveform_bottom), outline="#244668")
    for divider in range(1, 4):
        y = waveform_top + divider * (waveform_bottom - waveform_top) // 4
        draw.line((24, y, width - 24, y), fill="#132d46")
    draw.line((24, (waveform_top + waveform_bottom) // 2, width - 24, (waveform_top + waveform_bottom) // 2), fill="#2d5e80")
    plotted = signal[np.linspace(0, len(signal) - 1, num=width - 48, dtype=int)]
    centre = (waveform_top + waveform_bottom) / 2
    amplitude = (waveform_bottom - waveform_top) / 2 - 8
    points = [(24 + index, int(centre - value * amplitude)) for index, value in enumerate(plotted)]
    draw.line(points, fill="#35d2bd", width=1)
    draw.text((26, waveform_top + 7), "Waveform", fill="#a4c7de")

    # A bounded spectrogram makes the artifact predictable for large uploads.
    limited = signal[: min(len(signal), sample_rate * 120)]
    _, _, power = spectrogram(limited, fs=sample_rate, nperseg=min(1024, len(limited)), noverlap=0, mode="magnitude")
    if power.size:
        power = np.log1p(power)
        power = power[: min(128, power.shape[0]), : min(260, power.shape[1])]
        if power.size:
            scaled = (255 * (power - power.min()) / (np.ptp(power) or 1)).astype(np.uint8)
            spectral = Image.fromarray(scaled).resize((width - 48, 170), Image.Resampling.NEAREST).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            image.paste(spectral.convert("RGB"), (24, 288))
            draw.rectangle((24, 288, width - 24, 458), outline="#244668")
    draw.text((26, 267), "Log-magnitude spectrogram (first 120 seconds)", fill="#a4c7de")
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()


def analyse_audio(path: Path, max_seconds: int = 600) -> AudioAnalysisResult:
    """Review decodable WAV signals for transparent, non-verdict integrity signals.

    A loudness change, silence, clipping, or spectral pattern can arise in ordinary
    recording and transcoding. The function intentionally makes no automatic claim
    about speaker identity, synthetic speech, or legal authenticity.
    """
    if path.suffix.lower() != ".wav":
        raise ValueError("The local MVP currently supports waveform analysis for WAV evidence. MP3 evidence is preserved, but needs an approved decoder before analysis.")
    try:
        sample_rate, raw_samples = wavfile.read(path)
    except (ValueError, OSError) as exc:
        raise ValueError("The submitted evidence could not be decoded as an uncompressed WAV recording.") from exc
    if sample_rate <= 0 or raw_samples.size == 0:
        raise ValueError("The WAV recording contains no usable samples.")

    channels = 1 if raw_samples.ndim == 1 else raw_samples.shape[1]
    signal = _normalise(raw_samples)
    mono = signal if signal.ndim == 1 else np.mean(signal, axis=1)
    maximum_samples = sample_rate * max_seconds
    analysed = mono[:maximum_samples]
    duration_seconds = round(len(mono) / sample_rate, 3)
    block_size = max(256, sample_rate // 4)
    block_count = len(analysed) // block_size
    if block_count < 2:
        raise ValueError("The WAV recording is too short for a temporal integrity review.")
    blocks = analysed[: block_count * block_size].reshape(block_count, block_size)
    rms = np.sqrt(np.mean(np.square(blocks), axis=1))
    silence_threshold = max(0.0005, float(np.median(rms)) * 0.08)
    silent_runs = _find_runs(rms <= silence_threshold, minimum_length=4)
    energy_delta = np.abs(np.diff(rms))
    median_delta = float(np.median(energy_delta))
    mad_delta = float(np.median(np.abs(energy_delta - median_delta)))
    discontinuity_threshold = max(0.08, median_delta + 5 * mad_delta)
    discontinuities = np.where(energy_delta >= discontinuity_threshold)[0].tolist()
    clipped_fraction = float(np.mean(np.abs(analysed) >= 0.999))

    summary = {
        "sample_rate_hz": int(sample_rate),
        "channels": int(channels),
        "source_sample_dtype": str(raw_samples.dtype),
        "duration_seconds": duration_seconds,
        "analysed_duration_seconds": round(len(analysed) / sample_rate, 3),
        "block_duration_seconds": round(block_size / sample_rate, 4),
        "silence_threshold_rms": round(silence_threshold, 6),
        "energy_discontinuity_threshold": round(discontinuity_threshold, 6),
        "clipped_sample_fraction": round(clipped_fraction, 6),
    }
    silence_intervals = [
        {"start_seconds": round(start * block_size / sample_rate, 3), "end_seconds": round((end + 1) * block_size / sample_rate, 3)}
        for start, end in silent_runs[:20]
    ]
    discontinuity_times = [round((index + 1) * block_size / sample_rate, 3) for index in discontinuities[:30]]
    findings = [
        AudioForensicFinding(
            code="audio.signal.sampled",
            severity="info",
            title="WAV signal decoded for bounded review",
            detail="The local analysis measured waveform and spectral features over a bounded duration. It does not determine who spoke, whether a voice is synthetic, or whether the recording is legally authentic.",
            evidence=summary,
        ),
        AudioForensicFinding(
            code="audio.silence.intervals",
            severity="info",
            title="Sustained low-energy intervals identified" if silence_intervals else "No sustained low-energy intervals identified",
            detail="Silence can be normal in a recording. Listed intervals are navigational review markers, not evidence of deletion or editing.",
            evidence={"intervals": silence_intervals, "interval_count": len(silent_runs)},
        ),
        AudioForensicFinding(
            code="audio.energy.discontinuities",
            severity="review" if discontinuity_times else "info",
            title="Abrupt energy changes require context" if discontinuity_times else "No extreme block-energy changes",
            detail=(
                "Abrupt block-level loudness changes were found. Speech pauses, microphone movement, normal cuts, and automatic gain control can produce the same signal; inspect surrounding samples in the original recording."
                if discontinuity_times
                else "No block-level loudness changes crossed the adaptive review threshold in the analysed portion."
            ),
            evidence={"timestamps_seconds": discontinuity_times, "count": len(discontinuities), "threshold": round(discontinuity_threshold, 6)},
        ),
        AudioForensicFinding(
            code="audio.clipping",
            severity="review" if clipped_fraction >= 0.001 else "info",
            title="Potential clipping present" if clipped_fraction >= 0.001 else "No material clipping measured",
            detail="Clipping is a recording-quality signal and can be caused by ordinary gain settings. It does not by itself indicate manipulation.",
            evidence={"clipped_sample_fraction": round(clipped_fraction, 6), "review_threshold": 0.001},
        ),
    ]
    return AudioAnalysisResult(summary=summary, findings=findings, waveform_png=_render_audio_artifact(analysed, sample_rate))
