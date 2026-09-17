"""Reading a country out of a free-text location string.

This replaces a hand-maintained allowlist of German city names that was doing
duty as a country filter.  The allowlist had two failure modes and both were
silent:

* a posting in a German city nobody had thought of - Kassel, Kiel, Regensburg,
  Heilbronn - was dropped as "outside Germany target", with no way to tell that
  from a genuine foreign posting;
* the tool could only ever work for one country, because the country *was* the
  list.

The rule here instead: decide which country a location names, and compare that to
the profile's target countries.  **A location whose country cannot be determined
is kept.**  "Aachen", "Wendlingen am Neckar" and "Hybrid - 2 days on site" all
name no country, and dropping a posting because a string was terse is the same
silent-zero failure this project keeps finding.

Two-letter codes are only honoured as a whole comma-separated segment
("Berlin, DE"), never as a substring: "in" is India's code and also an English
preposition, and matching it loosely turns "Engineer in Munich" into an Indian
posting.
"""
from __future__ import annotations

import re
import unicodedata

#: country code -> the names it is written under, lowercased and unaccented.
#: Deliberately not exhaustive over all 249 ISO entries: it covers the markets a
#: jobseeker actually sees in postings, and anything unrecognised is *kept*, so a
#: gap here costs recall of the filter, never a lost posting.
COUNTRY_NAMES: dict[str, tuple[str, ...]] = {
    "de": ("germany", "deutschland", "allemagne", "germania"),
    "at": ("austria", "osterreich", "oesterreich"),
    "ch": ("switzerland", "schweiz", "suisse", "svizzera"),
    "fr": ("france", "frankreich"),
    "nl": ("netherlands", "the netherlands", "niederlande", "holland"),
    "be": ("belgium", "belgien", "belgique"),
    "lu": ("luxembourg", "luxemburg"),
    "dk": ("denmark", "danemark", "danmark"),
    "se": ("sweden", "schweden", "sverige"),
    "no": ("norway", "norwegen", "norge"),
    "fi": ("finland", "finnland", "suomi"),
    "is": ("iceland", "island"),
    "ie": ("ireland", "irland"),
    "gb": ("united kingdom", "great britain", "england", "scotland", "wales",
           "northern ireland", "uk"),
    "es": ("spain", "spanien", "espana"),
    "pt": ("portugal",),
    "it": ("italy", "italien", "italia"),
    "pl": ("poland", "polen", "polska"),
    "cz": ("czechia", "czech republic", "tschechien"),
    "sk": ("slovakia", "slowakei"),
    "hu": ("hungary", "ungarn", "magyarorszag"),
    "ro": ("romania", "rumanien"),
    "bg": ("bulgaria", "bulgarien"),
    "gr": ("greece", "griechenland"),
    "hr": ("croatia", "kroatien"),
    "si": ("slovenia", "slowenien"),
    "rs": ("serbia", "serbien"),
    "ee": ("estonia", "estland"),
    "lv": ("latvia", "lettland"),
    "lt": ("lithuania", "litauen"),
    "ua": ("ukraine",),
    "tr": ("turkey", "turkiye", "turkei"),
    "us": ("united states", "united states of america", "usa", "u.s.", "u.s.a."),
    "ca": ("canada", "kanada"),
    "mx": ("mexico", "mexiko"),
    "br": ("brazil", "brasilien", "brasil"),
    "ar": ("argentina", "argentinien"),
    "cn": ("china", "prc", "people's republic of china"),
    "hk": ("hong kong",),
    "tw": ("taiwan",),
    "jp": ("japan",),
    "kr": ("south korea", "korea", "republic of korea"),
    "in": ("india", "indien"),
    "sg": ("singapore", "singapur"),
    "my": ("malaysia",),
    "th": ("thailand",),
    "id": ("indonesia", "indonesien"),
    "ph": ("philippines",),
    "vn": ("vietnam",),
    "au": ("australia", "australien"),
    "nz": ("new zealand", "neuseeland"),
    "za": ("south africa", "sudafrika"),
    "eg": ("egypt", "agypten"),
    "ma": ("morocco", "marokko"),
    "ae": ("united arab emirates", "uae", "dubai"),
    "sa": ("saudi arabia", "saudi-arabien"),
    "il": ("israel",),
}

#: City / state names that identify a country unambiguously enough to be worth
#: recognising when the posting omits the country.  Only entries that are not
#: also common words elsewhere.  Absence from this table is not a rejection.
REGION_HINTS: dict[str, tuple[str, ...]] = {
    "de": ("baden-wurttemberg", "bayern", "bavaria", "nordrhein-westfalen",
           "north rhine-westphalia", "niedersachsen", "lower saxony", "hessen",
           "rheinland-pfalz", "sachsen", "sachsen-anhalt", "thuringen",
           "brandenburg", "schleswig-holstein", "mecklenburg-vorpommern", "saarland",
           "bremen", "nrw"),
    "us": ("california", "texas", "michigan", "massachusetts", "new york state"),
}

_STATE_CODES_US = {
    "al", "ak", "az", "ar", "co", "ct", "dc", "fl", "ga", "hi", "ia", "id", "il",
    "ks", "ky", "la", "md", "me", "mi", "mn", "mo", "ms", "mt", "nc", "nd", "ne",
    "nh", "nj", "nm", "nv", "ny", "oh", "ok", "or", "pa", "ri", "sc", "sd", "tn",
    "tx", "ut", "va", "vt", "wa", "wi", "wv", "wy",
}

REMOTE_MARKERS = ("remote", "anywhere", "home office", "homeoffice", "telearbeit",
                  "work from home", "hybrid")

_SPLIT = re.compile(r"[,/|()\[\]–—]|\s+-\s+")


def fold(text: str) -> str:
    """Lowercase and strip accents, so 'Österreich' and 'Oesterreich' agree."""
    if not text:
        return ""
    lowered = unicodedata.normalize("NFKD", str(text).lower())
    stripped = "".join(ch for ch in lowered if not unicodedata.combining(ch))
    return stripped.replace("ß", "ss").strip()


def segments(location: str) -> list[str]:
    return [s.strip() for s in _SPLIT.split(fold(location)) if s.strip()]


def is_remote(location: str) -> bool:
    folded = fold(location)
    return any(marker in folded for marker in REMOTE_MARKERS)


def detect_country(location: str) -> str | None:
    """The ISO-3166 alpha-2 code a location names, or None if it names none.

    None is a real answer and the caller must treat it as "unknown", not as
    "foreign".  Most ATS locations are bare city names.
    """
    if not location or not str(location).strip():
        return None
    parts = segments(location)
    if not parts:
        return None

    # 1) A full country name anywhere in the string, longest name first so
    #    "united states" wins over a stray "state".
    folded = " ".join(parts)
    best: tuple[int, str] | None = None
    for code, names in COUNTRY_NAMES.items():
        for name in names:
            if re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", folded):
                if best is None or len(name) > best[0]:
                    best = (len(name), code)
    if best is not None:
        return best[1]

    # 2) A bare two-letter code standing alone as its own segment.
    for part in reversed(parts):
        if len(part) == 2 and part.isalpha():
            if part in COUNTRY_NAMES:
                return part
            if part in _STATE_CODES_US:
                return "us"

    # 3) A state or province whose country is unambiguous.
    for code, hints in REGION_HINTS.items():
        for hint in hints:
            if re.search(rf"(?<![a-z]){re.escape(hint)}(?![a-z])", folded):
                return code
    return None


def matches_targets(location: str, targets: list[str] | None,
                    excluded: list[str] | None = None) -> tuple[bool, str]:
    """Does `location` belong in a search targeting `targets`?

    Returns (keep, reason).  Rules, in order:

    1. An explicit exclusion term in the profile always wins.
    2. No target countries configured -> everything is in scope.
    3. Remote/hybrid postings are kept: they are the ones a relocation-flexible
       candidate most wants to see.
    4. A recognised country is kept only if it is a target.
    5. An unrecognised country is **kept**, and the reason says so, because a
       terse location string is not evidence of anything.
    """
    text = fold(location)
    for term in (excluded or []):
        folded_term = fold(term)
        if not folded_term:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(folded_term)}(?![a-z0-9])", text):
            return False, f"location '{location}' matches the profile exclusion '{term}'"

    codes = [fold(t) for t in (targets or []) if str(t).strip()]
    if not codes:
        return True, "no target countries configured"
    if not text:
        return True, "posting states no location"
    if is_remote(location):
        return True, f"location '{location}' is remote or hybrid"

    country = detect_country(location)
    if country is None:
        return True, f"location '{location}' names no country; kept rather than guessed"
    if country in codes:
        return True, f"location '{location}' is in target country '{country}'"
    return False, (f"location '{location}' resolves to country '{country}', "
                   f"outside the target {codes}")
