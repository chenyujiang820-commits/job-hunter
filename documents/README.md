# Local Candidate Documents

Candidate source files are local-only and may use these extensions:

- PDF (`.pdf`)
- DOCX (`.docx`)
- Markdown (`.md`)
- plain text (`.txt`)

`tools/inventory_candidate_documents.py` reads only file metadata for these
extensions. It does not open, copy, modify, upload, or synchronize source
documents. Profile proposals are written separately under the local-only,
ignored `runtime/profile-proposals/` state directory; only explicitly confirmed
changes may update `profiles/candidate-profile.md`.

## Directory Layout

- `documents/`: local document root.
- `documents/candidate/`: candidate source files for the confirmed profile.
- `documents/templates/`: compatibility location for candidate document templates.
- `templates/`: tracked resume and cover-letter templates.
- `documents/generated/`: generated application materials; keep local.
- `runtime/profile-proposals/`: local-only reviewable profile proposals; ignored by Git.
- `mail/`: future local email-content storage; keep local and do not sync externally.

Do not add candidate data, generated resume or cover-letter files, tracker state, scraper state, or email contents to version control. Profile changes require explicit user confirmation.
