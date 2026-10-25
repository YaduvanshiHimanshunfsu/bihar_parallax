# Demo data policy

Do not place real police, victim, accused, banking, or confidential evidence in this repository.

- `samples/`: small, lawful original demo files.
- `synthetic_tampered/`: edits created by the team with documented methods.
- `ground_truth/`: labels that describe the original, the transformation, and expected forensic signals.

Every demo item needs a provenance note and SHA-256 hash in its accompanying manifest. Large datasets should be downloaded by scripts or documented here, not committed.
