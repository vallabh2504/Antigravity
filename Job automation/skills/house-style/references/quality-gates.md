# Application Quality Gates

Gates marked **(code)** are enforced by `jobauto app render` / `jobauto app finalize`.
The rest are the reviewer's job.

## Content gates

- Every number and proper term in the resume occurs in `facts/`. **(code)**
- Every claim is true to `facts/` in meaning, not only in vocabulary: no widened scope,
  no planned work shown as done, no job keyword presented as experience without support.
- Summary: three sentences, 55-75 words (code allows 45-90).
- Resume bullets: 14-32 words, one achievement each, ending with a period. **(code)**
- At most four bullets per role.
- Strict reverse chronology by start date. **(code)**
- Cover letter: 4 or 5 paragraphs, 380-450 words (code allows 340-475). **(code)**
- The letter names the company **(code)** and at least one paragraph fails the
  company-swap test because it is genuinely specific.
- No banned phrase, em or en dash, or replacement character. **(code)**
- Open questions (start date, supervisor, permit) are not answered by guessing.

## PDF gates

- A4 pages. **(code)**
- Resume exactly the configured page count (default 2); cover letter exactly one page. **(code)**
- The resume's last page carries real content, not a short spill. **(code)**
- Name and email extract as text; two independent extractors agree on reading order. **(code)**
- No replacement characters in extracted text. **(code)**
- No orphan headings, awkward breaks, wrapped one-word lines in the headline, clipped
  text or unbalanced white space (reviewer, from the page images).

## Readiness rule

`docs_ready` requires: machine gates pass, reviewer content and design scores at least
90, no blocker or major finding, and the review bound to the SHA-256 of the exact PDFs it
read. A weak fit, or an unanswered eligibility question, holds the application for the
candidate even when the documents pass.
