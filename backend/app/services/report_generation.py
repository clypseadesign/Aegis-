"""Report generation pipeline for AegisAI assessments.

Generates shareable report artifacts (JSON, Markdown) from execution
findings, evidence, and risk scores. Reports are written to a configured
output directory and the path is stored on the Report model.
"""

import json
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ProjectNotFoundError
from app.models.evidence import Evidence
from app.models.execution import Execution
from app.models.finding import Finding, FindingSeverity
from app.models.project import Project
from app.models.report import Report
from app.models.test import SecurityTest
from app.models.user import User
from app.services.projects import ensure_project_access
from app.services.risk_scoring import (
    compute_risk_level,
    compute_risk_score,
    execution_result_label,
    extract_test_category,
    map_category_to_owasp,
    severity_to_score,
)

DEFAULT_REPORT_DIR = Path(os.environ.get("AEGIS_REPORT_DIR", "/tmp/aegis/reports"))


def _report_dir(report_dir: Path | None = None) -> Path:
    base = report_dir or DEFAULT_REPORT_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base


def _count_by_severity(findings: list[dict]) -> dict[str, int]:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        sev = f["severity"].lower()
        counts[sev] = counts.get(sev, 0) + 1
    return counts


def _collect_report_data(
    session: Session,
    report: Report,
) -> dict:
    """Gather all data needed for a report from the database."""

    project = session.get(Project, report.project_id)
    executions = list(
        session.scalars(
            select(Execution)
            .where(Execution.project_id == report.project_id)
            .order_by(Execution.created_at)
        ).all()
    )

    finding_records: list[Finding] = []
    findings_data: list[dict] = []

    for execution in executions:
        test = session.get(SecurityTest, execution.test_id) if execution.test_id else None
        test_config = test.config if test else {}
        category = extract_test_category(test_config) if test_config else None
        owasp = map_category_to_owasp(category)

        exec_findings = list(
            session.scalars(
                select(Finding)
                .where(Finding.execution_id == execution.id)
                .order_by(Finding.created_at)
            ).all()
        )

        for finding in exec_findings:
            finding_records.append(finding)
            evidence = list(
                session.scalars(
                    select(Evidence)
                    .where(Evidence.finding_id == finding.id)
                    .order_by(Evidence.created_at)
                ).all()
            )
            findings_data.append(
                {
                    "id": str(finding.id),
                    "title": finding.title,
                    "description": finding.description,
                    "severity": finding.severity.value,
                    "severity_score": severity_to_score(finding.severity),
                    "status": finding.status.value,
                    "details": finding.details,
                    "owasp_category": owasp or "N/A",
                    "test_category": category or "unknown",
                    "evidence": [
                        {
                            "id": str(e.id),
                            "kind": e.kind,
                            "description": e.description,
                            "content": e.content,
                            "created_at": e.created_at.isoformat(),
                        }
                        for e in evidence
                    ],
                }
            )

    risk_score = compute_risk_score(finding_records)
    risk_level = compute_risk_level(finding_records)

    return {
        "project_id": str(report.project_id),
        "project_name": project.name if project else "unknown",
        "executions": [
            {
                "id": str(e.id),
                "test_id": str(e.test_id) if e.test_id else None,
                "status": e.status.value,
                "result": e.result.value,
                "result_label": execution_result_label(e.result),
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "error": e.error,
            }
            for e in executions
        ],
        "findings": findings_data,
        "risk_score": risk_score,
        "risk_level": risk_level.value,
        "total_findings": len(findings_data),
        "findings_by_severity": _count_by_severity(findings_data),
        "generated_at": datetime.now(UTC).isoformat(),
        # Overwritten by generate_report() with the assigned version number.
        "report_version": 0,
    }


def generate_report(
    session: Session,
    report: Report,
    report_dir: Path | None = None,
) -> str:
    """Generate a report artifact and store its path on the Report.

    Supports ``json`` and ``markdown`` formats. Returns the file path.
    """
    data = _collect_report_data(session, report)
    out_dir = _report_dir(report_dir)

    ext = report.format.lower() if report.format else "json"
    if ext not in ("json", "md", "markdown"):
        ext = "json"
    file_ext = "json" if ext == "json" else "md"

    report.version += 1
    data["report_version"] = report.version

    token = secrets.token_hex(4)
    base = f"report_{report.id}_v{report.version}_{token}"

    # The machine-readable snapshot is always written, so that report-to-report
    # comparison can read a historical run even after findings have changed.
    snapshot_path = out_dir / f"{base}.data.json"
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # The shareable artifact is the snapshot itself for JSON, a rendered
    # document for Markdown.
    if file_ext == "json":
        filepath = snapshot_path
    else:
        filepath = out_dir / f"{base}.md"
        _write_markdown_report(filepath, data)

    report.path = str(filepath)
    report.data_path = str(snapshot_path)
    report.generated_at = datetime.now(UTC)
    report.updated_at = datetime.now(UTC)
    session.commit()

    return str(filepath)


def _write_markdown_report(filepath: Path, data: dict) -> None:
    """Write a Markdown-formatted report from collected data."""

    lines: list[str] = []

    lines.append("# Security Assessment Report")
    lines.append("")
    lines.append(f"**Project:** {data['project_name']} (`{data['project_id']}`)")
    lines.append(f"**Generated:** {data['generated_at']}")
    lines.append(f"**Version:** {data['report_version']}")
    lines.append("")

    lines.append("## Risk Summary")
    lines.append("")
    lines.append(f"- **Risk Score:** {data['risk_score']}")
    lines.append(f"- **Risk Level:** {data['risk_level']}")
    lines.append(f"- **Total Findings:** {data['total_findings']}")
    lines.append("- **Findings by Severity:**")
    for sev, count in data["findings_by_severity"].items():
        lines.append(f"  - {sev.capitalize()}: {count}")
    lines.append("")

    lines.append("## Executions")
    lines.append("")
    lines.append("| ID | Result | Status | Started | Error |")
    lines.append("|---|---|---|---|---|")
    for exe in data["executions"]:
        started = exe["started_at"] or "—"
        error = exe["error"] or "—"
        lines.append(
            f"| `{exe['id'][:8]}` | {exe['result_label']} | {exe['status']} | {started} | {error} |"
        )
    lines.append("")

    lines.append("## Findings")
    lines.append("")
    if not data["findings"]:
        lines.append("No findings reported.")
        lines.append("")
    else:
        lines.append("| Title | Severity | OWASP | Category | Status |")
        lines.append("|---|---|---|---|---|")
        for f in data["findings"]:
            lines.append(
                f"| {f['title']} | {f['severity']} | {f['owasp_category']} "
                f"| {f['test_category']} | {f['status']} |"
            )
        lines.append("")

        for f in data["findings"]:
            lines.append(f"### {f['title']}")
            lines.append("")
            lines.append(f"**Severity:** {f['severity']} (score: {f['severity_score']})")
            lines.append(f"**OWASP Category:** {f['owasp_category']}")
            lines.append(f"**Test Category:** {f['test_category']}")
            lines.append(f"**Status:** {f['status']}")
            lines.append(f"**Description:** {f['description'] or '—'}")
            if f["details"]:
                lines.append(f"**Details:** `{json.dumps(f['details'])}`")
            if f["evidence"]:
                lines.append("")
                lines.append("**Evidence:**")
                for e in f["evidence"]:
                    lines.append(f"- [{e['kind']}] {e['description'] or ''}")
                    if e["content"]:
                        lines.append("```json")
                        lines.append(json.dumps(e["content"], indent=2))
                        lines.append("```")
            lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def require_project_report(
    session: Session,
    user: User,
    project_id: UUID,
    report_id: UUID,
) -> Report:
    """Authorize access to a single report and return it.

    Reports carry the full evidence set for an assessment, so every report
    route must confirm both that the report belongs to the given project and
    that the *caller* has access to that project. Checking only the path
    parameter would let anyone holding a project_id and report_id read another
    tenant's prompts and responses.
    """

    report = session.get(Report, report_id)
    if report is None or report.project_id != project_id:
        raise ProjectNotFoundError()

    project = session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError()
    ensure_project_access(session, user, project, "read")
    return report


def get_report_download_path(
    session: Session,
    report_id: UUID,
    project_id: UUID,
) -> Path:
    """Return the file path for a report download, raising if not found."""

    report = session.get(Report, report_id)
    if report is None or report.project_id != project_id:
        raise FileNotFoundError(f"report {report_id} not found")
    if not report.path:
        raise FileNotFoundError("report has not been generated yet")
    path = Path(report.path)
    if not path.exists():
        raise FileNotFoundError(f"report file not found: {path}")
    return path


def load_report_snapshot(
    session: Session,
    report_id: UUID,
    project_id: UUID,
) -> dict:
    """Load a report's persisted JSON data snapshot.

    Comparison reads the stored snapshot rather than live database state so
    that two historical runs can be compared even after the underlying
    findings and executions have changed.
    """

    report = session.get(Report, report_id)
    if report is None or report.project_id != project_id:
        raise FileNotFoundError(f"report {report_id} not found")

    if not report.data_path:
        raise FileNotFoundError("report has no data snapshot; generate it first")

    path = Path(report.data_path)
    if not path.exists():
        raise FileNotFoundError(f"report data snapshot not found: {path}")

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compare_reports(
    session: Session,
    report_a_id: UUID,
    report_b_id: UUID,
    project_id: UUID,
) -> dict:
    """Compare two report runs and return new/resolved/regressed findings.

    Both reports must belong to the supplied project and must have been
    generated (so that a data snapshot exists). Findings are matched by
    their ``(test_category, title)`` key. A finding present in B but not A
    is "new"; present in A but not B is "resolved"; present in both but
    with a higher severity in B is "regressed" (and lower severity in B is
    "improved").
    """

    def _index(report_id: UUID) -> dict[str, dict]:
        data = load_report_snapshot(session, report_id, project_id)
        return {f"{f['test_category']}|{f['title']}": f for f in data.get("findings", [])}

    a = _index(report_a_id)
    b = _index(report_b_id)

    new_findings: list[dict] = []
    resolved_findings: list[dict] = []
    regressed_findings: list[dict] = []
    improved_findings: list[dict] = []
    unchanged_findings: list[dict] = []

    for key, finding_b in b.items():
        finding_a = a.get(key)
        if finding_a is None:
            new_findings.append(finding_b)
            continue

        severity_before = finding_a["severity"]
        severity_after = finding_b["severity"]
        if severity_before == severity_after:
            unchanged_findings.append(finding_b)
            continue

        entry = {
            "title": finding_b["title"],
            "category": finding_b["test_category"],
            "severity_before": severity_before,
            "severity_after": severity_after,
            "owasp_category": finding_b.get("owasp_category", "N/A"),
        }
        if severity_to_score(FindingSeverity(severity_after)) > severity_to_score(
            FindingSeverity(severity_before)
        ):
            regressed_findings.append(entry)
        else:
            improved_findings.append(entry)

    for key, finding_a in a.items():
        if key not in b:
            resolved_findings.append(finding_a)

    return {
        "report_a_id": str(report_a_id),
        "report_b_id": str(report_b_id),
        "new_findings": new_findings,
        "resolved_findings": resolved_findings,
        "regressed_findings": regressed_findings,
        "improved_findings": improved_findings,
        "unchanged_findings": unchanged_findings,
        "new_count": len(new_findings),
        "resolved_count": len(resolved_findings),
        "regressed_count": len(regressed_findings),
        "improved_count": len(improved_findings),
        "unchanged_count": len(unchanged_findings),
    }


__all__ = [
    "DEFAULT_REPORT_DIR",
    "compare_reports",
    "generate_report",
    "get_report_download_path",
    "load_report_snapshot",
]
