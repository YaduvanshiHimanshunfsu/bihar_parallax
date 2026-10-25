# Parallax — six-minute demo script

## Before presenting

Start the application and run `python scripts/seed_demo.py` to create labelled, harmless team-created cases. Or prepare one harmless team-created JPEG, AVI, and WAV sample. Do not use real victim, suspect, or operational evidence in a public demonstration.

## 1. Lead with the forensic boundary — 20 seconds

“Parallax preserves original digital evidence, surfaces reproducible integrity signals, and prepares a structured dossier. It does not call a file fake or authentic; an authorised analyst remains responsible for the conclusion.”

## 2. Prove intake and custody — 45 seconds

Create a case and upload the JPEG. Point out the generated evidence ID, SHA-256 hash, immutable original storage, and audit event. Open the case and click **Re-hash stored original** to show that the current bytes match the intake record.

Open `DEMO-CUSTODY-001` and click **Verify custody audit** to show the linked event chain from intake through dossier generation. Explain that the local chain detects changed records, while production needs external anchoring or managed signing keys.

## 3. Show image review — 60 seconds

Open the image analysis. Explain the EXIF/timestamp checks and derived JPEG ELA heatmap. Use the finding detail to state that an editing-software tag or bright ELA region is a review lead, not proof of tampering.

## 4. Show CCTV review — 60 seconds

Upload a short AVI with a team-created repeated section. Open its case to show sampled frame references, near-duplicate candidates, abrupt transition leads, and the generated contact sheet. Mention that a static CCTV scene can produce duplicate signals, which is why the output asks for review.

## 5. Show audio review — 60 seconds

Upload a WAV with a team-created silence or loudness change. Show the waveform/spectrogram visual, timestamped energy markers, and clipping signal. State the current MVP does not claim to identify a person or synthetic voice; that would require a validated, licensed model and evaluation data.

## 6. Produce the dossier — 45 seconds

Click **Generate dossier**. Download the JSON, printable HTML, and PDF versions. Point out: original SHA-256, module versions, findings, derived-artifact hashes, custody events, and the mandatory human-review limitation statement.

## Judge-facing differentiator — 30 seconds

“Most hackathon projects show a single opaque AI score. Parallax makes every signal traceable to the original evidence, a bounded method, an artifact, and an audit event. Its strongest claim is therefore a defensible workflow—not an overconfident classifier.”
