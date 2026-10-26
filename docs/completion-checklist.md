# Parallax Completion Checklist

This checklist is the current implementation record for the PS-05 Digital Evidence Authenticity and Integrity Verification Platform. A checked item has been implemented and regression-tested in this repository; it is not a claim about production or legal admissibility.

## Completed in this implementation pass

- [x] Replace the active dark dashboard experience with a light, responsive Stitch-derived Parallax workbench.
- [x] Add a complete UI flow for Overview, Investigations, secure intake, case review, image/video/audio workspaces, custody audit, dossiers, analyst notes, and system safeguards.
- [x] Add bounded ORB feature-correspondence screening for spatially separated copy-move *candidates*, with clear false-positive and human-review warnings.
- [x] Connect the UI to the live FastAPI contract rather than using mock data:
  - `GET /api/v1/dashboard`, `/cases`, `/cases/{id}`, `/health`, and `/version`
  - secure case creation and multipart evidence intake
  - image, video, and audio analysis actions
  - evidence re-hashing, custody-chain verification, assessment, and dossier generation
  - analyst notes and dispositions
- [x] Preserve the original evidence separately from all generated artifacts and expose safe links to each.
- [x] Add a case-level human-decision layer. Notes and disposition changes are persisted and recorded in the custody history.
- [x] Fix the report-download exception path so an error does not raise an undefined-variable exception.
- [x] Enable SQLite WAL mode and a five-second busy timeout for safer concurrent local-demo access.
- [x] Add health and version endpoints for a clear UI readiness check.
- [x] Configure CORS from `PARALLAX_CORS_ORIGINS`, with safe local defaults for the single-origin MVP.
- [x] State the evidence boundary explicitly in the UI and reports: automated signals are leads for authorised human review, not a legal authenticity verdict.
- [x] Correct the secure-intake UI so every newly opened form suggests a fresh case reference rather than reusing a duplicate static reference.
- [x] Keep the UI truthful about the current audio boundary: WAV analysis is local; other validated audio originals can be preserved but require an approved decoder before analysis.

## Verified

- [x] Python test suite: `22 passed`.
- [x] Python source compilation for API, forensic engine, and helper scripts.
- [x] JavaScript syntax checks for both the new workbench and retained legacy script.
- [x] Docker Compose configuration validation.
- [x] Existing API integration tests cover evidence intake, image/video/audio analysis, reports, audit integrity, and the new analyst-note API.

## Demo checklist

- [ ] Start the application with the documented local command.
- [ ] Run `python scripts/seed_demo.py` to create labelled, harmless demo cases.
- [ ] In the UI, open an image case and show its original hash, ELA artifact, and metadata/timestamp findings.
- [ ] Open the CCTV/video case and show duplicate/transition leads plus the separate derived contact sheet.
- [ ] Open the WAV case and show waveform/spectrogram plus time-bound review leads.
- [ ] Use **Re-hash** to prove an unchanged stored original matches the intake SHA-256.
- [ ] Use **Verify custody audit** to validate the hash-linked history.
- [ ] Record an analyst note and show the new auditable event.
- [ ] Generate a dossier and open the PDF/HTML/JSON output.

## Deliberately not claimed as complete

- [ ] MP3/AAC decoding is not enabled because this environment has no approved FFmpeg/decoder runtime. The system must not pretend an MP3 analysis occurred.
- [ ] Analysis currently runs synchronously. A Redis-backed worker queue is the next scale-up step for large uploads.
- [ ] The hackathon MVP uses a demo analyst header, not production authentication, RBAC, rate limiting, or external audit anchoring.
- [ ] Copy-move detection, OCR of CCTV clock overlays, C2PA validation, and calibrated multi-source fusion require separate validation data and should only be added with tests and demonstrated limitations.
- [ ] No output should be described as court-admissible by itself; procedure, chain-of-custody policy, examiner validation, and jurisdictional rules remain outside software alone.

## Recommended next acceptance gate

Complete the demo checklist on the target machine with the intended sample files. Record the observed processing time, test one corrupt/unsupported input per media type, and only then claim a full end-to-end live demo.
