# jobauto

Find jobs that fit you, then let your own coding agent write the application:
a **planner** maps the job to your facts, a **writer** drafts a tailored resume and
cover letter, and an **independent reviewer** scores the rendered PDFs. Code gates
between the roles check every quote, every number and every PDF, so the agent
cannot skip a step or grade its own work.

Nothing is ever submitted for you. You approve jobs, you answer the questions only
you can answer, and you send the application.

```
fetch -> score -> dashboard: you approve
                      |
          "Prepare application"  ->  PROMPT.md  ->  paste into any agent
                      |
   planner -> check-plan -> writer -> render -> reviewer -> finalize
                  ^                      ^                     |
                  +---- FEEDBACK.md -----+------ revise -------+
                                                               |
                                    docs_ready  |  hold  |  needs_operator
```

## Install

Python 3.11 or newer (3.12 if you want the optional JobSpy boards).

```bash
git clone https://github.com/vallabh2504/Antigravity.git
cd "Antigravity/Job automation"
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -e .
```

**PDF rendering.** The default template is `rendercv-sb2nov`, which needs
[rendercv](https://github.com/rendercv/rendercv) in its own environment:

```bash
python -m venv .venv-rendercv
# Windows
.venv-rendercv\Scripts\pip install "rendercv[full]==2.8"
# macOS/Linux
.venv-rendercv/bin/pip install "rendercv[full]==2.8"
```

jobauto finds `.venv-rendercv` next to this README automatically, or set
`JOBAUTO_RENDERCV_PYTHON` to its interpreter. The HTML templates need Chrome or
Edge instead.

**Page images for the reviewer.** Install Poppler so `pdftoppm` is on your PATH
(`winget install poppler`, `brew install poppler`, `apt install poppler-utils`),
or set `JOBAUTO_PDFTOPPM`. Without it the reviewer only reads the PDF text.

## Set up your profile

```bash
jobauto init      # creates profile/config.yml, companies.yml, master_resume.yml, ...
```

Everything in `profile/` except the `*.example.yml` files is gitignored.

| File | What to put in it |
|---|---|
| `master_resume.yml` | Every true fact about you: roles, dates, bullets with numbers, education, skills, languages. The writer may use nothing else. See `examples/sample-candidate/master_resume.yml` for the shape. |
| `profile.md` | Optional: facts in prose (motivation, projects, what you want next). |
| `writer_answers.md` | Your answers to the planner's questions (start date, work permit, ...). |
| `writer_examples/*.json` | Optional: `content.json` of applications you were happy with. The writer copies their quality, never their facts. |
| `config.yml` | Search keywords, locations, scoring, and the `writer:` block (template, review rounds, minimum scores). |
| `companies.yml` | Companies whose career pages to watch. |

Then check the machine:

```bash
jobauto doctor
```

## Daily use: the dashboard

```bash
jobauto serve --open        # http://127.0.0.1:8000
```

1. **Fetch, score, report** pulls new postings and ranks them.
2. Open a job, read it, and click **Prepare application**. This approves the job and
   creates `Applications/<company-role>/` with a workspace and `PROMPT.md`.
3. Click **Copy prompt** and paste it into your agent: Claude Code, Codex, Cursor,
   Gemini CLI, or anything that can read files and run shell commands. Start the agent
   anywhere; the prompt contains absolute paths.
4. The agent runs planner, writer and reviewer, and calls a gate after each step.
   The dashboard shows the fit verdict, open questions, review scores per round and,
   at the end, the final PDFs.
5. If the planner raised questions, answer them in `profile/writer_answers.md` and
   click **Prepare application** again; the facts are refreshed and the agent can continue.

The job ends in one of three results:

| Result | Meaning |
|---|---|
| `docs_ready` | The reviewer passed both PDFs (scores at or above `min_scores`, no blocker or major finding). They are in `final/`, named for upload. |
| `hold` | The documents pass, but the fit is weak or an eligibility requirement is not met. Decide yourself. |
| `needs_operator` | The gates failed too often or the rounds ran out. Read `FEEDBACK.md` and `reviews/`. |

## The same from the command line

```bash
jobauto fetch && jobauto score && jobauto report
jobauto jobs --state scored
jobauto app prepare <job-id> --approve     # writes PROMPT.md
jobauto app status <job-id>
```

The gates the agent calls (you can call them too):

```bash
jobauto app check-plan <application-folder>
jobauto app render     <application-folder>
jobauto app finalize   <application-folder>
```

Each prints `RESULT:` and `NEXT:` and exits non-zero when the agent has to act.

**Unattended with Claude Code.** If the `claude` CLI is installed, `jobauto autopilot
<job-id>` (or **Run with Claude CLI** in the dashboard) runs the same kit with one
headless session per role. The reviewer never shares a session with the writer.

## Templates

Set `writer.templates` in `config.yml`. The first template is the one reviewed and
delivered; list more to render them side by side each round.

- rendercv: `rendercv-sb2nov` (default), `rendercv-classic`, `rendercv-engineeringresumes`, `rendercv-harvard`
- HTML: `html-karla-navy`, `html-scholar-serif`, `html-slate-band`, `html-margin-rail`

To compare all of them for a finished application:

```bash
jobauto templates Applications/<folder>/workspace/content.json
```

## What keeps the output honest

- **Plan gate:** every requirement quote must appear verbatim in the job description,
  every piece of evidence verbatim in your facts.
- **Fact lock:** every number and proper term in the resume must occur in your facts;
  the cover letter may also use terms from the job description.
- **Machine QA:** page count, fill of the last page, reading order, banned phrases,
  letter length, dashes.
- **Reviewer:** a separate role scores content and design against the page images and
  must bind its review to the SHA-256 of the exact PDFs it read. `finalize` recomputes
  the hashes, so an edited PDF or a self-written review does not pass.

More detail: [docs/workflow.md](docs/workflow.md).

## Tests

```bash
pip install -e ".[dev]"
pytest
```
