"""Namespace- and case-tolerant XML element access.

Why this module exists, recorded so the defect is not reintroduced: the Personio
adapter used to parse its XML feed with ``BeautifulSoup(text, "xml")`` and fall
back to ``"html.parser"``.  The ``"xml"`` feature needs ``lxml``; when ``lxml`` is
absent the constructor raises and the fallback silently takes over -- and
``html.parser`` **lowercases every tag name**.  Every lookup for a camelCase tag
(``createdAt``, ``employmentType``, ``jobDescriptions``) then matched nothing and
returned ``""``.  A posting's date silently became the empty string, which is the
same silent-zero class as a dead source reporting ``ok``.

XML is case-sensitive.  Parsing it with ``xml.etree.ElementTree`` (standard
library, no dependency, no optional feature to be missing) preserves case by
construction.  The helpers below additionally strip XML namespaces and match tag
names case-insensitively, so a feed that changes ``createdAt`` to ``createdat``
tomorrow is read rather than silently dropped.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Iterator


def local_name(tag: object) -> str:
    """``{http://ns}createdAt`` -> ``createdAt``; non-string tags -> ``""``."""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def parse_xml(text: str) -> ET.Element | None:
    """Parse XML text into an element tree, or ``None`` if it is not XML."""
    if not text or not isinstance(text, str):
        return None
    # A BOM or leading whitespace before the declaration is common in real feeds.
    payload = text.lstrip("﻿ \t\r\n")
    try:
        return ET.fromstring(payload)
    except ET.ParseError:
        return None


def iter_named(root: ET.Element, name: str) -> Iterator[ET.Element]:
    """Every descendant (and the root itself) whose local name matches `name`."""
    target = name.lower()
    if local_name(root.tag).lower() == target:
        yield root
    for el in root.iter():
        if el is root:
            continue
        if local_name(el.tag).lower() == target:
            yield el


def child(el: ET.Element, name: str) -> ET.Element | None:
    """The first child of `el` with the given local name, case-insensitively.

    Direct children win over deeper descendants: a ``<position>`` carries its own
    ``<name>`` *and* a ``<jobDescriptions>/<jobDescription>/<name>``, and a plain
    document-order walk would happily return the wrong one if a feed ever
    reordered the elements.
    """
    target = name.lower()
    for sub in el:
        if local_name(sub.tag).lower() == target:
            return sub
    for sub in el.iter():
        if sub is el:
            continue
        if local_name(sub.tag).lower() == target:
            return sub
    return None


def text_of(el: ET.Element | None) -> str:
    """All text inside `el`, including tail text of nested elements, stripped."""
    if el is None:
        return ""
    parts = ["".join(el.itertext())]
    return "".join(parts).strip()


def child_text(el: ET.Element, name: str) -> str:
    return text_of(child(el, name))
