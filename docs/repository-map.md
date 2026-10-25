# Repository map

| Location | Responsibility |
|---|---|
| `apps/web/` | Static HTML/CSS/JavaScript analyst dashboard, case review, integrity verification, and reports. |
| `services/api/` | FastAPI application: cases, custody records, media analysis orchestration, report assembly, and SQLite persistence. |
| `services/worker/` | Planned background job runner for long media analyses. |
| `forensic_engine/` | Pure, testable analysis modules. It must not contain HTTP handlers or UI code. |
| `forensic_engine/intake/` | MIME validation, hash calculation, immutable intake manifest. |
| `forensic_engine/metadata/` | EXIF/XMP/container parsing and consistency rules. |
| `forensic_engine/provenance/` | C2PA/content-credential validation and provenance findings. |
| `forensic_engine/image/` | ELA, JPEG/compression, copy-move, and optional ML localisation. |
| `forensic_engine/video/` | OpenCV sampled-frame timeline, near-duplicate/discontinuity leads, and contact sheets. |
| `forensic_engine/audio/` | WAV waveform/spectrogram, silence, loudness-transition, and clipping review. |
| `forensic_engine/fusion/` | Conservative signal aggregation and status recommendation. |
| `services/api/app/reports/` | Immutable JSON and printable HTML dossier storage. |
| `forensic_engine/evaluation/` | Metrics, test manifests, and benchmark runners. |
| `data/` | Safe, labelled demo inputs only; never operational evidence. |
| `scripts/` | Reproducible data setup, synthetic-tamper generation, evaluation, and verification commands. |
| `tests/` | End-to-end and evidence-integrity regression tests. |
| `infra/compose/` | Local container and service configuration. |

## Dependency direction

```text
web -> api -> worker -> forensic_engine
                 |          |
                 v          v
           database/storage  derived artifacts
```

`forensic_engine` must be callable from tests without starting the API, database, queue, or browser. This makes forensic findings easier to reproduce and defend.
