"""Tests for the rule-based finding classifier."""

from app.models.execution import ExecutionResult
from app.models.finding import FindingSeverity
from app.services.finding_classifier import classify_response, determine_execution_result


def test_no_config_produces_no_findings() -> None:
    assert classify_response("some response", None) == []


def test_empty_config_produces_no_findings() -> None:
    assert classify_response("some response", {}) == []


def test_no_patterns_produces_no_findings() -> None:
    config = {"grading": {"case_insensitive": True}}
    assert classify_response("some response", config) == []


def test_matching_pattern_produces_finding() -> None:
    config = {
        "grading": {
            "patterns": ["system prompt"],
            "case_insensitive": True,
        }
    }
    findings = classify_response("My system prompt is secret.", config)
    assert len(findings) == 1
    assert findings[0].severity == FindingSeverity.MEDIUM
    assert "system prompt" in findings[0].details["matched_patterns"]


def test_non_matching_pattern_produces_no_findings() -> None:
    config = {
        "grading": {
            "patterns": ["nonexistent pattern"],
            "case_insensitive": True,
        }
    }
    assert classify_response("nothing here", config) == []


def test_case_sensitive_matching() -> None:
    config = {
        "grading": {
            "patterns": ["SECRET"],
            "case_insensitive": False,
        }
    }
    findings = classify_response("this is a secret value", config)
    assert len(findings) == 0

    findings_upper = classify_response("this is a SECRET value", config)
    assert len(findings_upper) == 1


def test_min_matches_threshold() -> None:
    config = {
        "grading": {
            "patterns": ["secret", "password", "token"],
            "case_insensitive": True,
            "min_matches": 2,
        }
    }
    findings = classify_response("my secret password is here", config)
    assert len(findings) == 1
    assert len(findings[0].details["matched_patterns"]) == 2


def test_min_matches_not_reached() -> None:
    config = {
        "grading": {
            "patterns": ["secret", "password", "token"],
            "case_insensitive": True,
            "min_matches": 3,
        }
    }
    findings = classify_response("my secret password is here", config)
    assert findings == []


def test_severity_mapping() -> None:
    config = {
        "grading": {
            "patterns": ["leak"],
            "case_insensitive": True,
            "severity": "critical",
        }
    }
    findings = classify_response("data leak detected", config)
    assert len(findings) == 1
    assert findings[0].severity == FindingSeverity.CRITICAL


def test_invalid_severity_defaults_to_medium() -> None:
    config = {
        "grading": {
            "patterns": ["leak"],
            "case_insensitive": True,
            "severity": "unknown",
        }
    }
    findings = classify_response("data leak detected", config)
    assert len(findings) == 1
    assert findings[0].severity == FindingSeverity.MEDIUM


def test_custom_title() -> None:
    config = {
        "grading": {
            "patterns": ["inject"],
            "case_insensitive": True,
            "title": "Prompt injection suspected",
        }
    }
    findings = classify_response("try to inject this", config)
    assert len(findings) == 1
    assert findings[0].title == "Prompt injection suspected"


def test_default_title() -> None:
    config = {
        "grading": {
            "patterns": ["inject"],
            "case_insensitive": True,
        }
    }
    findings = classify_response("try to inject this", config)
    assert len(findings) == 1
    assert findings[0].title == "Potential security issue detected"


def test_multiple_patterns_all_matched() -> None:
    config = {
        "grading": {
            "patterns": ["secret", "password", "token"],
            "case_insensitive": True,
        }
    }
    findings = classify_response("secret password and token leaked", config)
    assert len(findings) == 1
    assert len(findings[0].details["matched_patterns"]) == 3


def test_judge_grading_without_judge_output_is_inconclusive() -> None:
    """An unavailable judge must not be reported as a pass.

    Reporting PASS here would be a false negative: the target would look
    safe purely because grading could not run.
    """

    config = {
        "grading": {
            "method": "judge_model",
            "patterns": ["system prompt"],
            "judge": {"pass_indicator": "safe", "fail_indicator": "vulnerable"},
        }
    }
    assert determine_execution_result([], config, judge_output=None) == ExecutionResult.INCONCLUSIVE


def test_judge_grading_with_findings_but_no_judge_output_is_inconclusive() -> None:
    config = {
        "grading": {
            "method": "judge_model",
            "patterns": ["system prompt"],
            "judge": {"pass_indicator": "safe", "fail_indicator": "vulnerable"},
        }
    }
    findings = classify_response("here is my system prompt", config)
    assert len(findings) == 1
    assert determine_execution_result(findings, config, judge_output=None) == (
        ExecutionResult.INCONCLUSIVE
    )


def test_judge_grading_uses_judge_output_when_available() -> None:
    config = {
        "grading": {
            "method": "judge_model",
            "patterns": ["system prompt"],
            "judge": {"pass_indicator": "safe", "fail_indicator": "vulnerable"},
        }
    }
    assert determine_execution_result([], config, judge_output="VERDICT: safe") == (
        ExecutionResult.PASS
    )
    assert determine_execution_result([], config, judge_output="VERDICT: vulnerable") == (
        ExecutionResult.FAIL
    )


def test_keyword_grading_still_passes_when_no_findings() -> None:
    config = {"grading": {"patterns": ["secret"], "case_insensitive": True}}
    assert determine_execution_result([], config) == ExecutionResult.PASS
