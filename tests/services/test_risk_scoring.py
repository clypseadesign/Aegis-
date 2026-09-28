"""Risk scoring tests for AegisAI."""

from app.models.finding import Finding, FindingSeverity
from app.services.risk_scoring import (
    RiskLevel,
    compute_risk_level,
    compute_risk_score,
    extract_test_category,
    map_category_to_owasp,
    severity_to_score,
)


def test_severity_to_score_returns_correct_values() -> None:
    assert severity_to_score(FindingSeverity.CRITICAL) == 10
    assert severity_to_score(FindingSeverity.HIGH) == 7
    assert severity_to_score(FindingSeverity.MEDIUM) == 5
    assert severity_to_score(FindingSeverity.LOW) == 2
    assert severity_to_score(FindingSeverity.INFO) == 1


def test_compute_risk_score_returns_max_severity() -> None:
    findings = [
        Finding(title="a", severity=FindingSeverity.LOW),
        Finding(title="b", severity=FindingSeverity.CRITICAL),
        Finding(title="c", severity=FindingSeverity.MEDIUM),
    ]
    assert compute_risk_score(findings) == 10


def test_compute_risk_score_empty_returns_zero() -> None:
    assert compute_risk_score([]) == 0


def test_compute_risk_level_critical() -> None:
    findings = [Finding(title="x", severity=FindingSeverity.CRITICAL)]
    assert compute_risk_level(findings) == RiskLevel.CRITICAL


def test_compute_risk_level_high() -> None:
    findings = [Finding(title="x", severity=FindingSeverity.HIGH)]
    assert compute_risk_level(findings) == RiskLevel.HIGH


def test_compute_risk_level_medium() -> None:
    findings = [Finding(title="x", severity=FindingSeverity.MEDIUM)]
    assert compute_risk_level(findings) == RiskLevel.MEDIUM


def test_compute_risk_level_low() -> None:
    findings = [Finding(title="x", severity=FindingSeverity.LOW)]
    assert compute_risk_level(findings) == RiskLevel.LOW


def test_compute_risk_level_none() -> None:
    assert compute_risk_level([]) == RiskLevel.NONE


def test_map_category_to_owasp_known() -> None:
    assert map_category_to_owasp("prompt_injection") == "LLM01:2025 – Prompt Injection"
    assert map_category_to_owasp("jailbreak") == "LLM01:2025 – Prompt Injection"
    assert (
        map_category_to_owasp("privacy_data_leakage")
        == "LLM3:2025 – Data Privacy & Confidentiality"
    )
    assert map_category_to_owasp("rag_attack") == "LLM10:2025 – Dependency Risk (RAG)"
    assert map_category_to_owasp("agent_tool_use") == "LLM8:2025 – Risk of Misuse (Agentic Abuse)"


def test_map_category_to_owasp_unknown_returns_none() -> None:
    assert map_category_to_owasp("unknown_category") is None
    assert map_category_to_owasp(None) is None


def test_extract_test_category_from_config() -> None:
    config = {"category": "prompt_injection", "grading": {}}
    assert extract_test_category(config) == "prompt_injection"


def test_extract_test_category_from_grading() -> None:
    config = {"grading": {"category": "jailbreak"}}
    assert extract_test_category(config) == "jailbreak"


def test_extract_test_category_missing_returns_none() -> None:
    assert extract_test_category({}) is None
    assert extract_test_category(None) is None
