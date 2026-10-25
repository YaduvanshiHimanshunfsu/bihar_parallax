# Parallax

**Digital Evidence Integrity Workbench — Bihar Cyber Hackathon PS-05**

Parallax helps an investigator preserve a submitted file, inspect metadata and provenance, run media-specific integrity checks, and prepare an evidence-backed report for human review.

The system must **not** declare a file legally authentic or fake. Its outputs are forensic indicators, source evidence, confidence, and limitations for an authorised reviewer.

## Build order

Build the project phase by phase. The source of truth is [the implementation plan](docs/implementation-plan.md).

1. Evidence intake and custody
2. Metadata and image forensics
3. CCTV/video integrity checks
4. Audio integrity checks
5. Case dashboard and reporting
6. Evaluation, hardening, and demo packaging

## Current MVP capabilities

| Area | Implemented now | Important boundary |
|---|---|---|
| Custody | File-signature validation, SHA-256 at intake, read-only original storage, audit log, on-demand re-hash | This local MVP uses SQLite and a demo analyst header; production needs real authentication and managed immutable storage. |
| Images | EXIF facts, timestamp consistency checks, editing-software context, JPEG ELA heatmap | ELA and metadata are review signals, not proof of editing. |
| Video/CCTV | Bounded sampled-frame similarity, near-duplicate candidates, abrupt-transition leads, contact sheet | It does not inspect every frame or prove deletion/insertion/reordering. |
| Audio | WAV waveform/spectrogram, silence, energy-transition, and clipping leads | It makes no speaker, deepfake, or authenticity verdict. MP3 is preserved but needs an approved local decoder before analysis. |
| Dossiers | Hashed JSON, printable HTML, and PDF dossier; report-generation audit event | Report output is an investigation aid and must retain the human-review notice. |

## Run locally

From the project root:

```powershell
cd services/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. The dashboard and API are served together. To run checks:

```powershell
cd services/api
python -m pytest -q
```

Or run the containerised local demo from the project root:

```powershell
docker compose up --build
```

To create harmless, labelled image, CCTV, and audio cases for the UI:

```powershell
python scripts/seed_demo.py
```

Use `--data-dir C:\temp\parallax-demo` to keep a presentation environment isolated from normal local data.

See [the demo script](docs/demo-script.md) for the recommended judge flow.
Read [the evaluation and limitation plan](docs/evaluation-plan.md) before making performance or accuracy claims.

## Repository map

See [the repository map](docs/repository-map.md) before placing code. Keep original evidence out of Git; only version small, safe, labelled sample files or their download instructions.

## Non-negotiable rules

- Calculate and retain a SHA-256 hash before analysis.
- Never overwrite the uploaded original.
- Hash every generated report and material derived artifact.
- Keep detector evidence separate from the final case status.
- Treat missing metadata, failed provenance validation, or one model score as a signal—not proof of tampering.
