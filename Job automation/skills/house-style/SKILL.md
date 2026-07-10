---
name: house-style
description: >
  The candidate's own writing voice, reverse-engineered from his 50 real résumé
  variants (skill/sources_resumes/). EVERY résumé, cover letter, and summary the
  application-writer produces MUST follow this. The point is that the output is
  indistinguishable from something Vallabh wrote himself: human, dense, technical,
  zero AI tells, and ZERO em-dashes.
---

# House Style — write like Vallabh, not like an AI

Source of truth: the real résumés in `Job automation/Resumes/Resume_Merged_1.txt` and `_2.txt`
(text extractions of ~50 real tailored résumé variants), plus `Resume_Prompt.txt` when supplied
for an application. Read them before writing. Match their voice exactly.

## The single most important rule
**NEVER use an em-dash (—) or use an en-dash (–) as a sentence connector.** His real
résumés contain none. Connect clauses with commas, colons, parentheses, semicolons, or
full stops. (An en-dash is allowed ONLY inside a date range, e.g. `09/2025 – 12/2025`.)
A stray "—" is an instant tell that an AI wrote it. There must be none.

## Banned AI tells (never write these)
- Em/en dashes as punctuation (see above).
- "I am writing to express", "keen interest", "I am confident that", "synergy", "delve",
  "tapestry", "in today's fast-paced world", "honed" (as a filler verb), "pivotal",
  "testament to", "spearheaded my journey", "an integrated contributor to", "a growing
  publication/track record" (when inflating a single item), "merging X with Y" / "combining
  X with Y" as the summary's framing verb.
- Rhetorical triads for their own sake ("faster, better, stronger").
- Vague filler ("various tasks", "many things", "cutting-edge solutions") with no specifics.
- Note on "leverage" and "passion(ate)": his real résumés use both idiomatically and
  repeatedly ("leveraging real-time competition data", "a deep passion for hydrogen
  mobility"), so they are NOT hard-banned. The tell is genericness, not the word: "passionate
  about cutting-edge solutions" is a tell; "a deep passion for hydrogen mobility, proven by
  leading Germany's only student FC vehicle" is his voice. Use them only when immediately
  backed by a specific, real proof point.

## His résumé bullet formula (copy this exactly)
Most bullets begin with a **bold thematic lead-in**, then a colon, then one dense,
specific sentence naming the real tools and the quantified result:

> **Fuel Cell Test Bench Development:** Engineered, fabricated, and electronically
> integrated a standalone fuel cell test bench, executing operational testing (purging,
> humidity cycling, short-circuiting) and performance data evaluation.

> **Strategy Implementation:** Architected and deployed advanced driving and fuel cell
> temperature control strategies using Simulink; leveraged real-time competition data to
> boost fuel efficiency by 80%, a critical factor in securing a runner-up finish at the
> Shell Eco-Marathon.

Rules for bullets:
- Strong opening verbs he actually uses: Engineered, Developed, Architected, Designed,
  Executed, Conducted, Performed, Led, Spearheaded, Oversaw, Managed, Validated,
  Prototyped, Integrated, Utilized, Drove, Benchmarked.
- Name the real tools every time: MATLAB/Simulink, CATIA V5, Siemens NX, Fusion 360,
  ANSYS (Structural, Fluent, ACP), Star-CCM+, MSC ADAMS, DMLS, Resin Infusion, Python,
  Power BI, CoppeliaSim, Siemens Teamcenter.
- Quantify with his real numbers: 80% efficiency, 25 kg mass reduction, 12% drag
  reduction, 150+ parts, DP/ECMS benchmarks, runner-up Shell Eco-Marathon 2025.
- One sentence per bullet (occasionally two). Dense, not padded.
- British/US spelling: follow the source. He writes "optimization/optimize" (z) but
  "fibre", "aluminium" and "aluminum" both appear. Prefer the JD's spelling; stay consistent.
- Capitalize real proper nouns and named systems (Fuel Cell, Simulink). Do not invent capitals.
- Verb variety: never reuse the same lead verb twice in one document (no "architected" x4).
- Rhythm: vary sentence length within a bullet-heavy or narrative section; do not chain three
  30+ word sentences in a row.
- Keep the strongest real number per role. Curation must never trade a hard number for a
  smoother sentence (e.g. the ~80% Shell Eco-Marathon efficiency gain must survive if that
  role is included at all).

## His summary formula
Two patterns he uses, both first person, PLUS a third-person variant when the application
explicitly requires it (see `Resume_Prompt.txt` for that application):
1. "A highly motivated Automotive Engineering Master's student [specializing in / with a
   strong focus on] X, Y, and Z. [Top-down] industrial simulation experience at Robert
   Bosch GmbH … [bottom-up] hands-on leadership at Ecogenium e.V. … Seeking [this role]
   to [apply specific expertise] at **<Company>** [for the specific JD topic]."
2. "As an Automotive Engineering Master's student, my career is purposefully aimed at
   advancing hydrogen mobility. … I am seeking <role> to <specific contribution> at <Company>."
3. Third-person (only when required): lead with a noun phrase ("Automotive Engineering
   Master's student at RWTH Aachen who has X, and now Y"), not the subjectless
   "Possesses/Combines/Seeking" verb-drop, that stilted construction is itself an AI tell even
   though it avoids "I". A light "he" is fine if third-person pronouns are allowed; check
   `Resume_Prompt.txt`'s own rules for whether they are.

The LAST sentence must name the target company and the JD's actual focus. This is how he
tailors. 3 to 5 lines. Confident, specific, dense. No clichés. State facts exactly as true,
never round "in review" up to "published" or "contributed to" up to "led".

## Cover-letter voice (derive from his summaries; he writes in this register)
- First person, plain, confident, specific. Sounds like a sharp engineer, not a marketer.
- Open with the single strongest, most JD-relevant real proof (e.g. the Bosch
  degradation/SOH work for a condition-monitoring role). No throat-clearing.
- Body: 1 to 2 short paragraphs of concrete proof points mapped to the JD, using real
  projects and numbers. Name tools.
- One honest "why this company / why now" line (sector, Stuttgart location, availability,
  visa if relevant), stated briefly.
- 250 to 330 words. No em-dashes. No boilerplate. Sign off simply.

## Self-check before returning (the writer MUST run this)
1. Search the text for "—" and "– " used as punctuation. If any exist, rewrite. Target: zero.
2. Scan for every banned phrase above. Remove.
3. Does each bullet name a real tool and (where possible) a number? If not, tighten.
4. Did curation drop any role's single strongest number? Put it back.
5. Is any lead verb repeated? Is any sentence over ~30 words, or are three long sentences
   chained in a row? Fix both.
6. Is any keyword written in more than one place (paragraph, Key-skills line, Skills section)
   with no added value? Give it a single home.
7. Are publications/claims stated exactly as true (no "in review" rounded up to "published")?
8. Read it aloud: does it sound like the source résumés? If it sounds "AI smooth", roughen
   it toward his denser, more technical register.
9. Is the summary's last line company-specific to THIS JD? It must be.
