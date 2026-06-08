"""jobauto — OpenClaw-driven job discovery & application assist pipeline.

Deterministic plumbing (fetch parsing, dedupe, storage, reporting) lives here.
The two stages that need intelligence/network — *fetching* portals and *LLM*
scoring/tailoring — are driven by the agent (OpenClaw, or Claude in-container)
via the CLI's exchange files. See SKILL.md.
"""

__version__ = "0.1.0"
