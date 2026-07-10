# Application packet: RWTH Aachen — Chair of Thermodynamics of Mobile Energy Conversion Systems (TME)

**Role:** Research Assistant/Associate (f/m/d) — PhD position in fuel cell systems
**Contact:** Prof. Marco Günther, +49 241 80-48080, bewerbungen@tme.rwth-aachen.de
**Application deadline:** 04/08/2026 (4 August 2026)

**One unified resume + cover letter covering all three open topics**, since all three are the
same chair, same contact, same "Your Profile" requirements, and same deadline — just three
specialization flavors of one PhD opening:

| Ref | Topic | Posting |
|---|---|---|
| V000011113 | SOFC fuel cells/systems (fuel flexibility, CHP, marine/aviation potential) | https://www.tme.rwth-aachen.de/go/id/kpjm/file/V000011113/lidx/1/ |
| V000011114 | PEM fuel cells/systems: 3D CFD (flow fields, bipolar plate, water transport, cold-start icing), test-bench validation | https://www.tme.rwth-aachen.de/go/id/kpjm/file/V000011114/lidx/1/ |
| V000011115 | PEM fuel cells/systems: aging effects, AI/Big Data analysis, lifetime & MPC models | https://www.tme.rwth-aachen.de/go/id/kpjm/file/V000011115/lidx/1/ |

## Why this fit
Leads with the DLR cathode-side control architecture work (0D lumped-parameter plant model +
feed-forward/PI/decoupler control, tuned against measurement data — the strongest, most recent
proof point) and the Ecogenium test-bench/troubleshooting work this season, then ties both to
all three topics: modeling/control for V113, measurement-correlated validation for V114, and
test-bench + KPI/degradation analysis for V115. SOFC is explicitly framed as *transferable
system-architecture knowledge*, not direct hands-on experience — he has none, and the letter
says so honestly.

## Fact-check pass (this revision)
Content was corrected against your direct input plus two real source resumes you provided,
saved in `../../Resumes/`. Key fixes: MPC is now "built" (not "designing"), added the DLR
balance-of-plant sizing tools / component selection / system rig work, added the GT Suite 1D
model and Dymola (Modelica — a direct match for the JD's "Matlab/Simulink or Modelica" line),
removed the incorrect "thermal-management digital twin" claim (the real digital twin is the
cathode-side plant model), corrected the Bosch degradation bullet to the stronger real phrasing,
added the confirmed second publication (IJSED, aircraft design, 11/2022) and corrected the Bosch
paper's status to "in review at SAE," added "Germany's only student-built hydrogen fuel-cell
vehicle," and removed the false claim of a specific Master's-thesis submission date (thesis
hasn't formally started; direction confirmed as fuel-cell system control, scope still open).

## Resume format (revised again)
The narrative-paragraph format (per `Resume_Prompt.txt`) was tried first, then hand-fixed for
craft issues, but still didn't read as genuinely his. Checked all ~50 real resumes in
`../../Resumes/`: every fuel-cell-targeted variant (DLR, EKPO, ElringKlinger, Fraunhofer) uses
his actual **bold-lead-in bullets**, not narrative paragraphs — narrative-with-Key-Skills only
shows up in his generalist, non-fuel-cell resumes (Porsche, general engineering). Since this
application is exactly the fuel-cell-target case, switched to match: bold thematic-lead-in
bullets (`**Theme:** dense sentence.`), no per-role Key Skills line (his real fuel-cell resumes
don't have one), a single Skills chips section at the end, and Ecogenium moved into its own
"Student Club" section, separate from "Experience" (DLR + Bosch) — this is his own real
structural convention, not an invention. The Summary now follows his actual real DLR-target
summary almost verbatim in structure ("A highly motivated... Possesses... Combines... Eager to
bring... to <Company>"), still third-person and still respects `Resume_Prompt.txt`'s "no first-
person pronouns" and "3-5 bolded phrases" rules. Several bullets reuse his real sentences close
to verbatim (e.g. the Ecogenium test-bench and Strategy Implementation bullets) rather than
paraphrasing, since fidelity to his actual documented wording was the point. The cover letter is
unaffected and stays first-person, since that register is normal for a cover letter regardless.

## Before you send — please confirm/edit
1. **Whether you actually want all three** — the letter applies to all three ref numbers with
   one packet. If you'd rather rank/prioritize one topic explicitly, or apply to only one or two,
   say so and I'll adjust.
2. **Additional documents German academic applications usually expect** — this chair's posting
   doesn't list required attachments beyond the application itself, but PhD applications at RWTH
   typically also want: transcripts (B.Tech + M.Sc.), a copy of the B.Tech degree certificate,
   and optionally reference letters. None of those are generated here — you'll need to attach
   your own PDFs when you send the email.
3. **Submission channel** — the posting says email is accepted but postal mail is recommended
   "for data protection reasons." Your call; email to bewerbungen@tme.rwth-aachen.de is the
   practical default.
4. **Still open / unconfirmed**: exact relevant-modules list for the M.Sc. (source resumes list
   different module sets depending on which job each was tailored for — I picked the most
   fuel-cell/control-relevant combination, please verify); German level shown as A2-B1 per
   `profile.md`, but the source resumes all say a flat "B1" — which is current?

## How to edit
- `resume.md` and `cover_letter.md` are yours to edit in plain Markdown — this is the content
  source of truth.
- Open `resume.html` / `cover_letter.html` in a browser: click **Edit** to change text inline
  (autosaves locally), **Download** to save, or **PDF** to print.
- `resume.html` / `cover_letter.html` were hand-built from the `skills/resume-writer/template.html`
  and `skills/cover-letter-writer/template.html` designs (skill chips, flex-aligned dates, accent
  colour) instead of the generic `jobauto render` CLI, which only has a plain markdown-to-HTML
  fallback (no chips, no visual hierarchy) and would downgrade the design if run here. **Don't
  run `python -m jobauto render rwth-tme-fuel-cell-systems-phd`** — after editing the Markdown,
  ask Claude to re-apply the changes to the HTML/PDF so the design is preserved.
