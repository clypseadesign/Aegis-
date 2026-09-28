"""Risk scoring and OWASP compliance mapping for AegisAI findings.

Maps findings to a numeric risk score based on severity and provides
OWASP LLM Top 10 classification for reporting and compliance purposes.
"""

from enum import StrEnum
from typing import Final

from app.models.execution import ExecutionResult
from app.models.finding import Finding, FindingSeverity

OWASP_LLM_TOP_10: Final[dict[str, str]] = {
    "prompt_injection": "LLM01:2025 – Prompt Injection",
    "jailbreak": "LLM01:2025 – Prompt Injection",
    "privacy_data_leakage": "LLM3:2025 – Data Privacy & Confidentiality",
    "rag_attack": "LLM10:2025 – Dependency Risk (RAG)",
    "agent_tool_use": "LLM8:2025 – Risk of Misuse (Agentic Abuse)",
}

SEVERITY_SCORES: Final[dict[FindingSeverity, int]] = {
    FindingSeverity.CRITICAL: 10,
    FindingSeverity.HIGH: 7,
    FindingSeverity.MEDIUM: 5,
    FindingSeverity.LOW: 2,
    FindingSeverity.INFO: 1,
}


class RiskLevel(StrEnum):
    """Aggregated risk level for a report or execution."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


def severity_to_score(severity: FindingSeverity) -> int:
    """Return the numeric risk score for a finding severity."""
    return SEVERITY_SCORES.get(severity, 5)


def compute_risk_score(findings: list[Finding]) -> int:
    """Compute the aggregate risk score for a set of findings.

    The score is the maximum severity score across all findings,
    reflecting the most severe issue found. Returns 0 when there
    are no findings.
    """
    if not findings:
        return 0
    return max(severity_to_score(f.severity) for f in findings)


def compute_risk_level(findings: list[Finding]) -> RiskLevel:
    """Return the aggregated risk level from a set of findings."""
    if not findings:
        return RiskLevel.NONE
    score = compute_risk_score(findings)
    if score >= 10:
        return RiskLevel.CRITICAL
    if score >= 7:
        return RiskLevel.HIGH
    if score >= 5:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def map_category_to_owasp(category: str | None) -> str | None:
    """Map a test case category string to its OWASP LLM Top 10 classification.

    Returns None if the category is unknown.
    """
    if category is None:
        return None
    return OWASP_LLM_TOP_10.get(category)


def extract_test_category(test_config: dict | None) -> str | None:
    """Extract the test case category from a SecurityTest's config dict."""
    config = test_config or {}
    category_str = config.get("category")
    if category_str is None:
        grading = config.get("grading", {})
        if isinstance(grading, dict):
            category_str = grading.get("category")
    return str(category_str) if category_str else None


def execution_result_label(result: ExecutionResult) -> str:
    """Return a human-readable label for an execution result."""
    return {
        ExecutionResult.PASS: "Pass",
        ExecutionResult.FAIL: "Fail",
        ExecutionResult.INCONCLUSIVE: "Inconclusive",
        ExecutionResult.NO_FINDINGS: "Pass (no findings)",
    }.get(result, "Inconclusive")


__all__ = [
    "OWASP_LLM_TOP_10",
    "RiskLevel",
    "SEVERITY_SCORES",
    "compute_risk_level",
    "compute_risk_score",
    "execution_result_label",
    "extract_test_category",
    "map_category_to_owasp",
    "severity_to_score",
]
