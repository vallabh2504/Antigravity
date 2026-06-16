# Resume — company- & role-specific resumes for Vallabh

Curated, ATS-friendly, photo-headed resumes tailored to a specific company and role.
Every line is drawn from the real master resume (`../skill/master_resume.yml`) and the
50 source variants (`../skill/sources_resumes/`). House style: zero em-dashes, his own
bold-lead-in bullet voice. Single-column body = ATS-safe; photo header = German-market
friendly.

## Files

| File | For | Accent |
|------|-----|--------|
| `Vallabh_Pataneni_Resume_Forschungszentrum_Juelich_Fuel_Cell_Systems.pdf` | Forschungszentrum Jülich — pure fuel-cell-systems engineer (air-cooled FC operation, control & EMS, full FCS development, sizing) | green |
| `Vallabh_Pataneni_Resume_Goldwind_Control_Strategy_Engineer.pdf` | Goldwind, Global Graduate Program 2026 — Control Strategy Engineer (Frankfurt) | blue |

Each PDF has a matching `.html` (editable in any browser) and is regenerated from
`build_resumes.py`. `profile_photo.jpg` is the headshot used in both headers.

## How to edit them in the future

**Easiest (content tweaks):** open the `.html` file in a browser to preview, edit the
text in `build_resumes.py` (the `juelich` and `goldwind` dicts hold every bullet,
skill chip, summary and date), then re-run:

```bash
cd "Job automation"
python3 Resume/build_resumes.py
```

This rewrites both the `.html` and the `.pdf`. Requirements: `weasyprint` and `Pillow`
(already in `../skill/requirements.txt`).

- To change a bullet: edit the `(lead-in, sentence)` tuples under `experience`.
- To add/remove a skill chip: edit the `skills` lists.
- To make a new company version: copy a dict, change `role`, `summary`, reorder
  `experience`, and add a `build(<dict>, "<filename>")` line at the bottom.
- To swap the photo: replace `profile_photo.jpg` (square crop works best) and re-run.

## Rules kept

- No em-dashes (the script asserts zero on every build).
- Nothing invented — only re-ordered / re-emphasised real experience.
- One page each, A4, print-ready.
