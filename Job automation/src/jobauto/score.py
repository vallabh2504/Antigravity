"""Stage 3: rules prefilter + scoring, driven by the operator's profile.

The best scoring mode is still the agent/LLM exchange (``build_score_tasks`` ->
``apply_scores``), because a model can reason over a whole job description.
``heuristic_score`` is the free deterministic fallback that keeps the scheduled
run useful with no API key.

**Why this module was rewritten.**  It used to hard-code one person's job hunt:
a literal list of ~60 city names standing in for "is this in my country", and
title keywords for one industry.  That had three consequences.

1. It was wrong for its own owner.  The city list *was* the country test, so a
   posting in a German city nobody had typed - Kassel, Kiel, Regensburg - was
   dropped with the reason "outside Germany target".  A missing string looked
   exactly like a genuinely foreign job.
2. It could not be given to anyone else.  Changing industry or country meant
   editing Python, not configuration.
3. Its drop reasons lied.  The include-keyword rejection named one industry's
   keywords regardless of which profile terms had actually been checked.

Everything domain-specific now comes from the configuration.  With an empty
config this module filters nothing and scores on structure alone - seniority,
description completeness, date quality, eligibility restrictions - which is the
honest behaviour for "I was told nothing about what you want".
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from . import geo
from .db import DB

#: Base score before any profile signal is applied.
BASE_SCORE = 38


# --------------------------------------------------------------- profile reads

def _terms(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    return [str(v).strip().lower() for v in (value or []) if str(v).strip()]


def target_countries(cfg: dict) -> list[str]:
    """ISO-3166 alpha-2 codes the profile is searching in."""
    raw = cfg.get("target_countries")
    if raw is None:
        raw = cfg.get("search_country")
    return [c.lower() for c in _terms(raw)]


def _scoring(cfg: dict) -> dict:
    block = cfg.get("scoring")
    return block if isinstance(block, dict) else {}


def _hit(text: str, terms: list[str]) -> str:
    """The first profile term present in `text` as a whole word, or ''."""
    for term in terms:
        if not term:
            continue
        pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
        if re.search(pattern, text):
            return term
    return ""


# ------------------------------------------------------------- location shims
#
# ``tools/verify_scoping.py`` imports these two names and calls them with no
# configuration, so they stay, but they are now thin wrappers over ``geo`` and
# over the operator's own profile rather than over a baked-in city list.

def _profile() -> dict:
    try:
        from . import config
        return config.load_config() or {}
    except Exception:
        return {}


def is_foreign_location(loc_text: str, excluded_locs: list[str] | None = None) -> bool:
    """True when `loc_text` is positively identified as outside the target set.

    Note the asymmetry, which is the whole point of the rewrite: a location this
    function cannot place is **not** foreign.  Returning True on an unrecognised
    string is what silently deleted in-country postings from the operator's own
    run.
    """
    cfg = _profile()
    excluded = excluded_locs if excluded_locs is not None else cfg.get("excluded_locations")
    keep, _ = geo.matches_targets(loc_text, target_countries(cfg), _terms(excluded))
    return not keep


def is_german_location(loc_text: str, allowed_locations: list[str] | None = None) -> bool:
    """Back-compatible alias for "is this location in scope for the profile?".

    The name is historical - the check is now whichever countries the profile
    targets.  ``allowed_locations``, when given, is treated as an additional
    allowlist that keeps a posting regardless of the country test.
    """
    cfg = _profile()
    text = geo.fold(loc_text)
    for allowed in _terms(allowed_locations):
        if allowed and allowed in text:
            return True
    keep, _ = geo.matches_targets(loc_text, target_countries(cfg),
                                  _terms(cfg.get("excluded_locations")))
    return keep


def location_in_scope(location: str, cfg: dict) -> tuple[bool, str]:
    """(keep, reason) for one posting location against one profile."""
    for allowed in _terms(cfg.get("priority_locations")):
        if allowed and allowed in geo.fold(location):
            return True, f"location '{location}' is a profile priority location"
    return geo.matches_targets(location, target_countries(cfg),
                               _terms(cfg.get("excluded_locations")))


# ------------------------------------------------------------------- filtering

def hard_filter(job: dict, cfg: dict) -> tuple[bool, str]:
    """Cheap rules to drop obvious misses before spending scoring effort.

    Every rejection reason names the profile setting that caused it, so a run
    that returns nothing can be diagnosed from the report alone.
    """
    from .util import contains_keyword

    text = f"{job.get('title') or ''} {job.get('jd_text') or ''}".lower()
    include = [k for k in (cfg.get("include_keywords") or []) if str(k).strip()]
    if include and not any(contains_keyword(text, k) for k in include):
        return False, f"matches none of the {len(include)} profile include_keywords"
    for term in (cfg.get("exclude_keywords") or []):
        if contains_keyword(text, term):
            return False, f"matches the profile exclude_keyword '{term}'"

    location = str(job.get("location") or "").strip()
    if location:
        keep, reason = location_in_scope(location, cfg)
        if not keep:
            return False, reason
    return True, "passed rules"


def build_score_tasks(db: DB, cfg: dict, profile: str, limit: int = 50) -> dict[str, Any]:
    """Emit unscored jobs (after rules) for the agent to score."""
    tasks = []
    dropped = []
    for job in db.unscored():
        keep, reason = hard_filter(job, cfg)
        if not keep:
            db.set_score(job["id"], 0, {"reasons": [reason], "tier": "filtered"})
            dropped.append({"id": job["id"], "reason": reason})
            continue
        tasks.append({
            "id": job["id"],
            "company": job["company"],
            "title": job["title"],
            "location": job["location"],
            "url": job["url"],
            "jd_excerpt": (job["jd_text"] or "")[:4000],
        })
        if len(tasks) >= limit:
            break

    sectors = "|".join(s["name"] for s in _sectors(cfg)) or "as relevant"
    priority = ", ".join(_terms(cfg.get("priority_locations"))) or "no stated preference"
    return {
        "instructions": (
            "For each job, return an object {id, score (0-100 fit against the candidate "
            f"profile below), reasons (2-4 short bullets), sector ({sectors}|other), "
            "language_required (\"\"|A2|B1|B2|C1), visa_friendly_guess (true|false|null; "
            "null when the posting is silent), is_phd (bool), tier (A=top target|B|C)}. "
            "Weight relevance to the profile's own keywords and sector order first, then "
            f"location (priority locations: {priority}). Flag rather than zero a role whose "
            "language requirement exceeds the candidate's stated level."
        ),
        "profile": profile,
        "jobs": tasks,
        "dropped_by_rules": dropped,
    }


def apply_scores(db: DB, scores: list[dict]) -> int:
    n = 0
    for s in scores:
        jid = s.get("id")
        if not jid or not db.get(jid):
            continue
        meta = {k: s.get(k) for k in
                ("reasons", "sector", "german_required", "visa_friendly_guess", "is_phd", "tier",
                 "seniority", "degree_required", "eligibility_flags", "jd_completeness",
                 "posted_date_quality", "deadline_quality", "scoring_mode")}
        # The agent is asked for `language_required`; the stored column is the
        # older `german_required`. Accept either rather than dropping the value.
        if not meta.get("german_required") and s.get("language_required"):
            meta["german_required"] = s["language_required"]
        db.set_score(jid, int(s.get("score", 0)), meta)
        n += 1
    return n


# --------------------------------------------------------------------- scoring

def _sectors(cfg: dict) -> list[dict]:
    """Profile sector definitions: [{name, terms, bonus}], most wanted first."""
    raw = _scoring(cfg).get("sectors") or cfg.get("sectors") or []
    if isinstance(raw, dict):
        raw = [{"name": k, "terms": v} for k, v in raw.items()]
    out: list[dict] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        terms = _terms(entry.get("terms"))
        if not name or not terms:
            continue
        # The default bonus decays with the order the operator listed them in, so
        # a profile can express preference just by ordering the list.
        bonus = entry.get("bonus")
        out.append({"name": name, "terms": terms,
                    "bonus": int(bonus) if bonus is not None else max(4, 12 - 3 * index)})
    return out


def _penalties(cfg: dict) -> list[dict]:
    """Profile penalties: [{reason, terms, points, scope, unless_primary}].

    ``scope`` is ``title`` or ``text``; ``unless_primary`` suppresses the penalty
    when the title already matched a primary profile term, which is how "a
    battery role is a miss unless it is also the thing I search for" is expressed
    without naming any industry in code.
    """
    out: list[dict] = []
    for entry in _scoring(cfg).get("penalties") or []:
        if not isinstance(entry, dict):
            continue
        terms = _terms(entry.get("terms"))
        if not terms:
            continue
        out.append({
            "reason": str(entry.get("reason") or f"profile penalty on {terms[0]}"),
            "terms": terms,
            "points": int(entry.get("points") or 10),
            "scope": "title" if str(entry.get("scope") or "text") == "title" else "text",
            "unless_primary": bool(entry.get("unless_primary")),
        })
    return out


def heuristic_score(job: dict, cfg: dict) -> dict[str, Any]:
    """Free deterministic fallback scorer, entirely profile-driven.

    With an empty `cfg` this returns a structure-only score: no keyword can
    promote or demote a job, because none were configured.  That is deliberate -
    inventing a domain for an operator who stated none is how the previous
    version came to rank one industry for everybody.
    """
    title = (job.get("title") or "").lower()
    jd = (job.get("jd_text") or "").lower()
    text = f"{title} {jd}"
    raw_loc = str(job.get("location") or "")
    loc = raw_loc.lower().strip()

    if loc:
        keep, why = location_in_scope(raw_loc, cfg)
        if not keep:
            return {
                "id": job["id"],
                "score": 0,
                "reasons": [why],
                "sector": "filtered",
                "german_required": "",
                "language_required": "",
                "visa_friendly_guess": False,
                "is_phd": False,
                "seniority": "unspecified",
                "degree_required": "unspecified",
                "eligibility_flags": ["location_out_of_scope"],
                "jd_completeness": _jd_completeness(job.get("jd_text", "")),
                "posted_date_quality": _posted_date_quality(job.get("posted_at", "")),
                "deadline_quality": _deadline_quality(text),
                "tier": "filtered",
                "scoring_mode": "free-heuristic",
            }

    scoring = _scoring(cfg)
    primary = _terms(scoring.get("primary_terms")) or _terms(cfg.get("include_keywords"))
    secondary = _terms(scoring.get("secondary_terms"))
    skills = _terms(scoring.get("skill_terms")) or _terms(cfg.get("skills"))

    score = int(scoring.get("base", BASE_SCORE))
    reasons: list[str] = []
    eligibility_flags: list[str] = []

    primary_in_title = _hit(title, primary)
    if primary_in_title:
        score += 30
        reasons.append(f"title matches the profile term '{primary_in_title}'")
    else:
        primary_in_jd = _hit(jd, primary)
        if primary_in_jd:
            score += 15
            reasons.append(f"description matches the profile term '{primary_in_jd}'")

    secondary_in_title = _hit(title, secondary)
    if secondary_in_title:
        score += 15
        reasons.append(f"title matches the secondary profile term '{secondary_in_title}'")
    else:
        secondary_in_jd = _hit(jd, secondary)
        if secondary_in_jd:
            score += 8
            reasons.append(f"description matches the secondary profile term '{secondary_in_jd}'")

    skill_hit = _hit(text, skills)
    if skill_hit:
        score += 10
        reasons.append(f"overlaps the profile skill '{skill_hit}'")

    sector = "other"
    for entry in _sectors(cfg):
        hit = _hit(text, entry["terms"])
        if hit:
            sector = entry["name"]
            score += entry["bonus"]
            reasons.append(f"matches the '{entry['name']}' sector on '{hit}'")
            break

    for penalty in _penalties(cfg):
        haystack = title if penalty["scope"] == "title" else text
        hit = _hit(haystack, penalty["terms"])
        if not hit:
            continue
        if penalty["unless_primary"] and primary_in_title:
            continue
        score -= penalty["points"]
        reasons.append(f"{penalty['reason']} ('{hit}')")

    priority_hit = next((p for p in _terms(cfg.get("priority_locations")) if p and p in loc), "")
    if priority_hit:
        score += 8
        reasons.append(f"in the profile priority location '{priority_hit}'")
    elif loc and geo.is_remote(loc):
        score += 3
        reasons.append("remote-compatible location")
    elif loc and geo.detect_country(loc) in target_countries(cfg):
        score += 4
        reasons.append("in a target country")

    seniority = _seniority(text)
    if seniority in ("lead", "manager", "director"):
        score -= 18
        reasons.append(f"{seniority}-level seniority is above the target level")
        eligibility_flags.append("seniority_high")
    elif seniority == "senior":
        score -= 10
        reasons.append("senior-level experience requirement")
        eligibility_flags.append("seniority_senior")

    degree_required = _degree_requirement(text)
    if degree_required == "phd":
        score -= 12
        reasons.append("PhD is stated as a requirement")
        eligibility_flags.append("phd_required")

    language_required = _language_requirement(text, cfg)
    if language_required in ("B2", "C1", "C2"):
        score -= 12 if language_required == "B2" else 20
        reasons.append(f"posting indicates {language_required}-level local-language proficiency")
        eligibility_flags.append("language_advanced")

    restriction_terms = {
        "security_clearance": ("security clearance", "sicherheitsüberprüfung",
                               "sicherheitsueberpruefung"),
        "citizenship_required": ("citizenship required", "citizens only", "citizen only",
                                 "staatsangehörigkeit erforderlich"),
        "work_authorization_required": ("must have unrestricted work authorization",
                                        "no visa sponsorship", "cannot sponsor",
                                        "existing work permit required",
                                        "valid work permit required"),
    }
    for flag, terms in restriction_terms.items():
        if any(term in text for term in terms):
            eligibility_flags.append(flag)
    visa_positive = any(term in text for term in
                        ("visa sponsorship", "visa support", "relocation and visa",
                         "work permit support"))
    visa_restricted = any(f in eligibility_flags for f in
                          ("citizenship_required", "work_authorization_required"))
    visa_friendly: bool | None
    if visa_restricted:
        visa_friendly = False
    elif visa_positive:
        visa_friendly = True
    else:
        visa_friendly = None
    if any(f in eligibility_flags for f in
           ("citizenship_required", "work_authorization_required", "security_clearance")):
        score -= 20
        reasons.append("citizenship, work-authorisation, or clearance restriction")

    jd_completeness = _jd_completeness(job.get("jd_text", ""))
    if jd_completeness == "missing":
        score -= 8
        reasons.append("job description missing; eligibility cannot be assessed (reduced penalty)")
    elif jd_completeness == "thin":
        score -= 4
        reasons.append("job description is too short for reliable eligibility scoring "
                       "(reduced penalty)")

    posted_date_quality = _posted_date_quality(job.get("posted_at", ""))
    deadline_quality = _deadline_quality(text)
    if posted_date_quality == "exact":
        score += 2
    elif posted_date_quality == "missing":
        score -= 2

    score = max(0, min(100, score))
    return {
        "id": job["id"],
        "score": score,
        "reasons": reasons[:6] or ["relevant enough for human review"],
        "sector": sector,
        "german_required": language_required,
        "language_required": language_required,
        "visa_friendly_guess": visa_friendly,
        "is_phd": bool(re.search(
            r"(?<![a-z])(phd|doctoral|wissenschaftlicher mitarbeiter)(?![a-z])", text)),
        "seniority": seniority,
        "degree_required": degree_required,
        "eligibility_flags": eligibility_flags,
        "jd_completeness": jd_completeness,
        "posted_date_quality": posted_date_quality,
        "deadline_quality": deadline_quality,
        "tier": "A" if score >= 82 else "B" if score >= 65 else "C",
        "scoring_mode": "free-heuristic",
    }


def _seniority(text: str) -> str:
    title = text[:300]
    if re.search(r"\b(director|head of|vp|vice president)\b", title):
        return "director"
    if re.search(r"\b(manager|team lead|technical lead|lead engineer)\b", title):
        return "manager" if "manager" in title else "lead"
    if re.search(r"\bsenior\b|\bsr\.?\b", title) or re.search(r"\b(?:5|6|7|8|9|10)\+? years", text):
        return "senior"
    if re.search(r"\bjunior\b|\bgraduate\b|\bentry.level\b", title):
        return "entry"
    return "unspecified"


def _degree_requirement(text: str) -> str:
    if re.search(r"(?:ph\.?d|doctorate).{0,35}(?:required|essential|must|vorausgesetzt)", text):
        return "phd"
    if re.search(r"(?:master(?:'s)?|m\.?sc\.?|diplom).{0,45}(?:required|degree|abschluss)", text) \
            or re.search(r"(?:required|degree|abschluss).{0,45}(?:master(?:'s)?|m\.?sc\.?|diplom)",
                         text) \
            or re.search(r"postgraduate(?: [a-z][a-z-]*){0,3} degree", text):
        return "master"
    if re.search(r"(?:bachelor(?:'s)?|bsc).{0,35}(?:required|degree|abschluss)", text):
        return "bachelor"
    return "unspecified"


#: How each working language names itself in a posting, and the CEFR level each
#: phrasing implies.  Keyed by language so a profile targeting another country
#: gets the same treatment; no candidate's own level is encoded here.
_LANGUAGE_PHRASES: dict[str, dict[str, tuple[str, ...]]] = {
    "de": {
        "name": ("german", "deutsch"),
        "C1": ("native german", "muttersprachliche deutschkenntnisse",
               "verhandlungssicheres deutsch", "verhandlungssichere deutschkenntnisse"),
        "B2": ("fluent german", "fließende deutschkenntnisse", "fliessende deutschkenntnisse",
               "sehr gute deutschkenntnisse", "very good german"),
        "B1": ("good german", "gute deutschkenntnisse", "german required",
               "deutschkenntnisse erforderlich"),
    },
    "fr": {
        "name": ("french", "francais", "français"),
        "C1": ("native french", "francais natif"),
        "B2": ("fluent french", "very good french"),
        "B1": ("good french", "french required"),
    },
    "nl": {
        "name": ("dutch", "nederlands"),
        "C1": ("native dutch",),
        "B2": ("fluent dutch", "very good dutch"),
        "B1": ("good dutch", "dutch required"),
    },
    "es": {
        "name": ("spanish", "espanol", "español"),
        "C1": ("native spanish",),
        "B2": ("fluent spanish", "very good spanish"),
        "B1": ("good spanish", "spanish required"),
    },
}

#: The working language a target country implies, where it is unambiguous enough
#: to act on.  A country absent here simply gets no language check.
_COUNTRY_LANGUAGE = {"de": "de", "at": "de", "ch": "de", "fr": "fr", "be": "fr",
                     "nl": "nl", "es": "es", "mx": "es", "ar": "es"}


def _language_requirement(text: str, cfg: dict | None = None) -> str:
    """CEFR level the posting demands in the local working language, or ''.

    Which language counts is derived from the profile's target countries, or from
    ``scoring.language`` when the operator states it outright.  With no profile
    at all every supported language is checked, because a posting that demands
    C1 in *some* language is information the candidate wants either way.
    """
    cfg = cfg or {}
    langs = _terms(_scoring(cfg).get("language"))
    if not langs:
        langs = [_COUNTRY_LANGUAGE[c] for c in target_countries(cfg) if c in _COUNTRY_LANGUAGE]
    if not langs:
        langs = list(_LANGUAGE_PHRASES)

    levels = {"a2": 1, "b1": 2, "b2": 3, "c1": 4, "c2": 5}
    explicit: list[str] = []
    for lang in langs:
        spec = _LANGUAGE_PHRASES.get(lang)
        if not spec:
            continue
        names = "|".join(re.escape(n) for n in spec["name"])
        explicit += re.findall(rf"\b(a2|b1|b2|c1|c2)\b.{{0,45}}(?:{names})", text)
        explicit += re.findall(rf"(?:{names}).{{0,45}}\b(a2|b1|b2|c1|c2)\b", text)
    if explicit:
        return max(explicit, key=lambda item: levels[item]).upper()

    for lang in langs:
        spec = _LANGUAGE_PHRASES.get(lang)
        if not spec:
            continue
        for level in ("C1", "B2", "B1"):
            if any(phrase in text for phrase in spec.get(level, ())):
                return level

    # German has two idiomatic phrasings that no fixed phrase list catches.
    if "de" in langs:
        if re.search(r"verhandlungssicher.{0,25}deutsch|deutsch.{0,25}verhandlungssicher", text):
            return "C1"
        if re.search(r"(?:fließend|fliessend|sehr gut).{0,25}deutsch"
                     r"|deutsch.{0,25}(?:fließend|fliessend)", text):
            return "B2"
    return ""


def _jd_completeness(jd_text: str) -> str:
    plain = " ".join((jd_text or "").split())
    if not plain:
        return "missing"
    if len(plain) < 350:
        return "thin"
    markers = sum(term in plain.lower() for term in
                  ("responsibil", "requirements", "qualifications", "aufgaben", "profil",
                   "benefits"))
    return "complete" if len(plain) >= 900 or markers >= 2 else "usable"


def _posted_date_quality(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return "missing"
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
        return "exact"
    except ValueError:
        return ("relative"
                if re.search(r"\b(today|yesterday|ago|heute|gestern|vor)\b", text.lower())
                else "unparsed")


def _deadline_quality(text: str) -> str:
    if re.search(r"(?:deadline|apply by|bewerbungsfrist).{0,30}"
                 r"(?:\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b)", text):
        return "exact"
    if any(term in text for term in ("rolling basis", "open until filled", "laufend")):
        return "rolling"
    return "missing"


def auto_score(db: DB, cfg: dict, limit: int = 200) -> int:
    """Score unscored jobs with the deterministic fallback scorer."""
    n = 0
    for job in db.unscored():
        keep, reason = hard_filter(job, cfg)
        if not keep:
            db.set_score(job["id"], 0, {
                "reasons": [reason],
                "sector": "filtered",
                "german_required": "",
                "visa_friendly_guess": False,
                "is_phd": False,
                "tier": "filtered",
                "scoring_mode": "free-heuristic",
            })
            n += 1
            continue
        score = heuristic_score(job, cfg)
        db.set_score(job["id"], int(score["score"]), score)
        n += 1
        if n >= limit:
            break
    return n


#: Historic alias: the older name for the language check, kept because the field
#: it feeds is still called ``german_required`` in the database schema.
_german_requirement = _language_requirement
