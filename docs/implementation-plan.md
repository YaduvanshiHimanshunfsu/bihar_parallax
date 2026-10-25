# Parallax implementation plan

## Operating rule

Finish each phase's acceptance criteria before expanding scope. A working evidence-custody and metadata workflow is more valuable than several unverified ML widgets.

## Phase 1 — Foundation and evidence integrity

**Goal:** establish a reproducible case/evidence record before analysing any media.

### Build in this order

1. Initialise the API and web applications, formatter, linter, test runner, and local Docker Compose services.
2. Define the core data contracts: `Case`, `EvidenceItem`, `DerivedArtifact`, `AnalysisRun`, `Finding`, and `AuditEvent`.
3. Implement file-type validation, streamed SHA-256 hashing, safe object-storage paths, and original-file immutability.
4. Add case creation, evidence upload, evidence-detail, and audit-trail endpoints.
5. Build the minimal web flow: create case → upload file → display hash and custody event.
6. Seed two harmless demo cases: one original and one team-created altered file.

### Primary locations

- `services/api/app/models/`, `schemas/`, `db/`, `api/routes/`
- `forensic_engine/intake/`
- `apps/web/src/features/cases/` and `features/intake/`
- `tests/evidence_integrity/`

### Deliverables

- Upload works for approved image, audio, and video extensions.
- Every accepted file receives an evidence ID, SHA-256, intake timestamp, and custody entry.
- Originals and generated artifacts have separate storage paths and hashes.

### Acceptance criteria

- Uploading the same bytes twice results in the same SHA-256.
- Changing one byte changes the hash.
- The original object is never modified by analysis.
- Invalid MIME signatures, oversized files, and disallowed extensions are rejected with useful errors.

---

## Phase 2 — Metadata, provenance, and image forensics

**Goal:** make image evidence inspectable through deterministic checks before optional ML.

### Build in this order

1. Integrate ExifTool or an equivalent extractor behind a small adapter.
2. Store normalized metadata findings: capture time, modification time, GPS availability, software tags, dimensions, colour profile, and missing/invalid fields.
3. Add rules for conflicting timestamps and suspicious editing-software tags; describe them as indicators, never verdicts.
4. Implement JPEG Error Level Analysis and save the heatmap as a derived artifact.
5. Add a basic compression/quantisation summary and a copy-move candidate module.
6. Add C2PA validation as an optional provenance finding; missing credentials must be neutral.
7. Render metadata, provenance, heatmap, raw finding details, and limitations in the case view.

### Primary locations

- `forensic_engine/metadata/`, `provenance/`, `image/`
- `services/api/app/services/`
- `apps/web/src/features/image-forensics/`

### Deliverables

- Image evidence page with original preview, SHA-256, metadata table, findings, and ELA artifact.
- JSON analysis output that retains tool version, parameters, and artifact hashes.

### Acceptance criteria

- A legitimate recompressed image does not automatically receive a high-concern outcome.
- Every ELA heatmap links to its source evidence and processing parameters.
- The UI states that no detected signal is not proof of authenticity.

---

## Phase 3 — CCTV and video integrity analysis

**Goal:** identify potential missing, duplicated, inserted, or reordered frames with reviewable evidence.

### Build in this order

1. Parse container and stream facts with FFprobe: duration, codec, frame rate, time base, streams, and timestamps.
2. Extract a bounded frame timeline; queue long files instead of blocking an API request.
3. Calculate perceptual frame hashes and flag near-duplicate sequences.
4. Add adjacent-frame similarity and temporal discontinuity signals.
5. Produce a review timeline with suspicious ranges, thumbnails, source frames, and scores.
6. Add optional visible-clock OCR only after the core timeline works.

### Primary locations

- `forensic_engine/video/`
- `services/worker/app/`
- `apps/web/src/features/video-forensics/`

### Deliverables

- Video summary, processing progress, duplicate-frame candidates, and discontinuity timeline.
- One labelled demo video with intentionally duplicated or removed frames.

### Acceptance criteria

- The system returns a segment range and supporting frame references, not merely one opaque score.
- A static scene is marked as requiring review rather than automatically labelled tampered.
- Analysis can be retried safely without changing the original evidence record.

---

## Phase 4 — Audio integrity analysis

**Goal:** surface possible audio edits and synthetic-speech indicators as time-bound review leads.

### Build in this order

1. Validate audio container, sample rate, channels, duration, and codec.
2. Generate a waveform and spectrogram as derived artifacts.
3. Segment speech/silence and identify abrupt energy, spectral, or background-noise changes.
4. Return candidate splice windows with reasons and confidence.
5. Add an optional anti-spoof/deepfake model only if its model card, licence, and failure modes are documented.
6. Display the findings on a scrub-able audio timeline.

### Primary locations

- `forensic_engine/audio/`
- `apps/web/src/features/audio-forensics/`
- `services/worker/app/`

### Deliverables

- Audio detail page with waveform, spectrogram, and candidate time segments.
- One clean and one team-created splice example with known ground truth.

### Acceptance criteria

- Findings identify an exact time range and evidence type.
- Codec changes and noisy audio reduce confidence rather than generating overconfident conclusions.
- Any ML score is visible as one signal among others.

---

## Phase 5 — Fusion, analyst workflow, and forensic dossier

**Goal:** turn raw signals into a reviewable investigation case rather than a collection of charts.

### Build in this order

1. Define the controlled outcome vocabulary: `provenance_validated`, `no_integrity_concern_detected`, `needs_expert_review`, `high_integrity_concern`, and `inconclusive`.
2. Implement conservative, explainable fusion rules. Preserve every contributing signal and never hide contradictory results.
3. Add analyst notes, disposition, and review checklist.
4. Assemble a versioned JSON Evidence Integrity Dossier.
5. Render a printable HTML report containing hashes, methods, tool versions, findings, artifact links, confidence, and limitations; add PDF export only after the report contents are stable.
6. Hash the final report and record report generation in the audit log.

### Primary locations

- `forensic_engine/fusion/`, `reporting/`
- `services/api/app/services/`
- `apps/web/src/features/reports/`

### Deliverables

- A complete case view and downloadable JSON/printable HTML dossier.
- An analyst can see why a status was recommended and override it with a recorded reason.

### Acceptance criteria

- No status can be presented without links to its underlying findings.
- The dossier identifies the original file hash, all derived artifacts, and analysis versions.
- The report always includes a limitation statement and a human-review notice.

---

## Phase 6 — Evaluation, security hardening, and demo readiness

**Goal:** prove the MVP is reliable enough to demonstrate and make its limitations explicit.

### Build in this order

1. Create labelled ground-truth manifests for every demo item.
2. Write unit tests for hashing, metadata rules, image output, temporal-segment creation, audio-segment creation, and fusion rules.
3. Write integration tests for upload-to-report and retry-safe analysis.
4. Measure analysis time, detector precision/recall where labels exist, false positives on recompressed legitimate files, and report completeness.
5. Add security checks: role enforcement, upload-size limits, path traversal prevention, malicious-file handling, secrets scan, and audit-log integrity checks.
6. Package Docker Compose, seeded demo data, a one-command startup guide, and a six-minute demo script.

### Primary locations

- `forensic_engine/evaluation/`
- `scripts/`
- `tests/`, `infra/compose/`, `.github/workflows/`
- `docs/demo-script.md`

### Deliverables

- Test results and an honest evaluation table.
- Offline-ready demo environment.
- Three cases: image edit, CCTV/video temporal anomaly, and audio splice/synthetic-risk example.

### Acceptance criteria

- A fresh machine can start the demo from documented commands.
- Each demo conclusion can be traced to stored evidence artifacts.
- The team can explain one false-positive risk per media type and how the product handles it.

## Recommended task split

| Workstream | Main phases | Responsibility |
|---|---|---|
| Platform and custody | 1, 5, 6 | API, data model, storage, audit, report generation, security |
| Image and provenance | 2, 6 | Metadata, C2PA, ELA, image artifacts, evaluation |
| Video and audio | 3, 4, 6 | Worker pipeline, temporal analysis, audio analysis, labelled cases |
| Frontend and demo | 1–6 | Analyst workflows, visual evidence, usability, demo narrative |

## Scope guardrails

- Do not train a new deepfake model before the deterministic workflows work.
- Do not implement OCR, C2PA, or anti-spoofing until their predecessor pipeline is testable.
- Do not call an anomaly a crime, a forged file, or legally admissible proof.
- If a module fails, retain intake, metadata, hashing, ELA, frame hashes, waveform, and report generation as the demonstrable fallback.
