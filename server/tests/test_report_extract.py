"""
The JSON extractor's wrappings, each one bought with a lost report.

Free-tier models wrap their answers four ways so far: reasoning preamble,
markdown fences, a sentence of introduction, and — the expensive one — a
stray opening brace before the real object, which cost a complete and
correctly-scoped report during upstream saturation on 2026-09-01.
"""

from __future__ import annotations

from newsterminal.report import extract_json

REPORT = '{"bias": "bearish", "conviction": 2, "nested": {"a": [1, 2], "b": "x{y}"}}'


def test_bare_object() -> None:
    assert extract_json(REPORT)["bias"] == "bearish"


def test_reasoning_preamble() -> None:
    got = extract_json("Let me look at the gamma structure first. " + REPORT)
    assert got and got["conviction"] == 2


def test_markdown_fence() -> None:
    got = extract_json("Here is the note:\n```json\n" + REPORT + "\n```\n")
    assert got and got["bias"] == "bearish"


def test_the_stray_opening_brace() -> None:
    """The 2026-09-01 shape: '{' then the actual report, whole and valid."""
    got = extract_json("{\n\n" + REPORT)
    assert got and got["bias"] == "bearish"
    assert got["nested"]["b"] == "x{y}"


def test_two_strays_still_recover() -> None:
    got = extract_json("{ {\n" + REPORT + "\ntrailing prose")
    assert got and got["conviction"] == 2


def test_braces_inside_strings_do_not_confuse_the_walk() -> None:
    got = extract_json('junk { not json } more junk ' + REPORT)
    # The first balanced object is "{ not json }" which does not parse; the
    # walk must move on and find the real one.
    assert got and got["bias"] == "bearish"


def test_no_object_is_none() -> None:
    assert extract_json("the model apologised and produced nothing") is None
    assert extract_json("") is None
    assert extract_json("{ never closes") is None
