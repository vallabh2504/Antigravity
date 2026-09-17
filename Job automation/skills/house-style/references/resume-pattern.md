# Resume Pattern

## Content architecture

Use one of two explicit modes:

- `industry_one_page`: header, 55-70 word summary, selected experience, technical skills, education.
- `research_two_page`: page 1 header, 55-75 word summary, experience; page 2 selected projects/research, education, technical skills, publication/recognition, languages.

The pipeline default is two pages (`resume.pages: 2`). Use one page only when the
candidate's config asks for it.

## Summary

Write three compact sentences:

1. Identity and specialization.
2. Two or three strongest evidence anchors, preferably with system scale or validation.
3. Engineering contribution relevant to the target role, without naming the company merely to appear tailored.

Target 55-75 words. Hard maximum 90 words. Never open with `Highly motivated` or `Seeking a position`.

## Experience order

Use strict reverse chronology. Keep current/recent relevant work first. Relevance determines bullet selection, not date order.

## Bullet grammar

Construct each bullet as:

`Action + engineering object + method/tool + purpose/constraint + evidence`

Evidence means at least one of:

1. measured outcome;
2. validation or benchmark;
3. physical/system scale;
4. delivered artifact;
5. operational constraint.

Examples of acceptable shapes:

- `Modeled and validated [system] in MATLAB/Simulink against [reference data], establishing [engineering use].`
- `Designed [controller/subsystem] using [method] to regulate [variables] under [constraint].`
- `Characterized [hardware] through [test methods], identifying [operating behavior or limit].`

Rules:

- Prefer 14-32 words and one achievement per bullet; end every bullet with a period.
- Use 3-4 bullets for the most relevant role and 2-3 for older roles.
- Start with a distinct strong verb: Developed, Modeled, Validated, Designed, Implemented, Calibrated, Optimized, Integrated, Characterized, Quantified, Benchmarked, Automated, Led.
- Do not append detached `Key Skills:` phrases to experience bullets.
- A tool name alone is not evidence.
- Use keywords only where supported and grammatically natural.

## Skills

Use four plain ATS-safe category rows, comma-separated. Do not use chips, proficiency ratings, icons, stars, or progress bars.

Name the categories after the target job's domain, for example:

- <Core domain> Systems
- Modelling and Simulation
- Data and Optimisation
- Engineering Tools

## Remove

Do not include date of birth, portrait, full street address, declaration, signature image, generic objective, or personal-status information unless explicitly requested.
