"""Application writer: planner -> writer -> reviewer, with code gates in between.

* :mod:`kit`      - builds an application folder and the agent prompt for one job.
* :mod:`gates`    - the deterministic checks an agent runs between roles.
* :mod:`autopilot`- runs the same roles and gates headlessly with the Claude CLI.
* :mod:`facts`    - the fact corpus and fact lock.
* :mod:`plan`     - provenance checks on the planner's plan.
* :mod:`render`, :mod:`themes`, :mod:`rendercv_engine` - templates and PDF QA.
"""
from __future__ import annotations

SCHEMA = "jobauto.application.v2"
