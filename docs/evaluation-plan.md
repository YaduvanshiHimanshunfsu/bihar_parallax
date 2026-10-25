# Parallax — evaluation and limitation plan

## What is currently demonstrated

The checked-in automated suite validates deterministic implementation behaviour: safe file-signature intake, immutable original storage, SHA-256 re-verification, image analysis and derived artifacts, AVI sequence review, WAV review, dossier creation, and conservative assessment rules.

Run it from `services/api`:

```powershell
python -m pytest -q
```

The seeded demo cases are labelled team-created media. They are useful to verify the full workflow, including a fresh custody-chain case; they are **not** a scientific benchmark and must not be presented as accuracy evidence.

## Evaluation dataset to assemble before a production claim

| Media | Needed examples | Ground truth | Primary measures |
|---|---|---|---|
| JPEG images | Camera originals, ordinary re-exports, known edits | Original/edit history and edit regions where available | Review-signal precision/recall; false-review rate on benign re-exports; analysis latency |
| CCTV/video | Continuous clean clips, static scenes, team-created duplicate/deletion/insert examples | Exact affected frame intervals | Interval-level recall, false-positive ranges per hour, contact-sheet correctness, processing time per minute |
| WAV audio | Clean recordings, varied devices/codecs, team-created splice/level-change samples | Exact affected time ranges | Candidate-window recall, false positives per minute, range-boundary error, processing time |
| Reports | Cases covering every analysis outcome | Expected hashes, audit events, artifacts, and limitation statement | Report completeness rate and hash verification success |

Keep a CSV/JSON manifest with the source, consent/licence, creation method, ground-truth ranges, and split (`development`, `holdout`, `demo`). Never tune thresholds on the holdout split.

## Proposed MVP acceptance targets

These are targets to test, not measured results.

| Area | Proposed target | Why it matters |
|---|---:|---|
| Intake hash | 100% match on immediate re-hash of accepted test files | Custody baseline |
| Original preservation | 0 original-byte changes after analysis | Evidence integrity |
| Artifact linkage | 100% artifacts linked to a source evidence item and analysis run | Reproducibility |
| Report completeness | 100% generated dossiers include hash, tool version, limitations, and custody events | Analyst/judge traceability |
| Benign JPEG review rate | Establish a measured ceiling from held-out re-exports before deployment | Controls ELA/metadata overclaiming |
| Video/audio signal quality | Report precision and recall only after labelled ranges are available | Avoids invented detector scores |

## Known limitations and honest presentation

- Image metadata and ELA are indicators, not a tamper verdict. Many messaging or editing workflows legitimately remove or change metadata.
- Video analysis samples frames and does not yet parse every container timestamp, run FFprobe, or prove frame insertion/deletion/reordering.
- Audio analysis currently supports decodable WAV only. MP3 can be preserved but needs an approved local decoder; there is no speaker-identification or deepfake claim.
- The local hackathon mode uses SQLite and a demo analyst identity. Production requires authenticated role-based access, managed immutable/object storage, retention policy, encrypted backups, and an independent audit-log strategy.
- New local audit events are hash-chained per case and can expose changed event data. The chain is not a replacement for external anchoring or a managed signing key; someone with unrestricted database and application control could rewrite both data and hashes.
- JSON, printable HTML, and PDF dossiers are implemented. The final legal/reporting template still needs approval before operational use.

## Self-challenge before judging

A strong competing team may offer FFprobe container analysis, C2PA validation, a validated anti-spoof model, or a polished graph of media provenance. Those additions are more difficult to copy than our dashboard visual design.

Parallax should compete on traceability: preserve the original first; expose each tool version, parameter, artifact hash, and limitation; and make the analyst re-hash, assessment, and dossier workflow visible in the live demo. The greatest live-demo risks are an unsupported MP3, a long/corrupt video, or an API/server setup issue. Use the seeded, local JPEG/AVI/WAV cases; keep the raw files and generated reports local; and show the fallback—intake, hashing, and report generation—even if a media-specific analyser fails.

The strongest next technical improvement is an asynchronous worker that performs full video timestamp/container inspection and records per-segment source-frame ranges. It would materially improve both forensic depth and reliability without replacing the current evidence-custody foundation.
