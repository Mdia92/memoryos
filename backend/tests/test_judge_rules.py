"""LongMemEval judge — deterministic rules fallback (no LLM)."""

from evals.longmemeval.judge import _normalize, _rules_grade


def test_normalize_lowercases_and_strips_punct():
    assert _normalize("Business Administration!") == "business administration"


def test_normalize_strips_accents():
    assert _normalize("Café Ampèré") == "cafe ampere"


def test_normalize_collapses_whitespace():
    assert _normalize("a  \t  b\n c") == "a b c"


def test_rules_grade_exact_substring_correct():
    r = _rules_grade("You graduated with Business Administration", "Business Administration")
    assert r["correct"] is True


def test_rules_grade_case_and_punct_insensitive():
    r = _rules_grade("Yes! You have BUSINESS ADMINISTRATION.", "business administration")
    assert r["correct"] is True


def test_rules_grade_missing_gold_marked_wrong():
    r = _rules_grade("You graduated with Computer Science", "Business Administration")
    assert r["correct"] is False


def test_rules_grade_high_token_overlap_still_correct():
    r = _rules_grade(
        "graduated business administration degree from state",
        "business administration",
    )
    assert r["correct"] is True


def test_rules_grade_low_token_overlap_wrong():
    r = _rules_grade("I don't know that", "Business Administration")
    assert r["correct"] is False


def test_rules_grade_empty_gold_wrong():
    r = _rules_grade("something", "")
    assert r["correct"] is False
    assert "empty" in r["reason"]
