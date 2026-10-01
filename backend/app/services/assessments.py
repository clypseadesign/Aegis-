"""Security test, execution, finding, evidence, and report service operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import (
    AssessmentNotFoundError,
    ExecutionBindingError,
    ProjectNotFoundError,
)
from app.models.evidence import Evidence
from app.models.execution import Execution, ExecutionStatus
from app.models.finding import Finding, FindingStatus
from app.models.project import Project
from app.models.report import Report
from app.models.target import Target, TargetStatus
from app.models.test import SecurityTest
from app.models.user import User
from app.schemas import (
    EvidenceCreate,
    ExecutionCreate,
    FindingCreate,
    FindingUpdate,
    ReportCreate,
    SecurityTestCreate,
    SecurityTestUpdate,
)
from app.services.audit import record_audit_event
from app.services.projects import ensure_project_access
from app.services.severity_scorer import compute_automatic_severity


def _require_project(session: Session, user: User, project_id: UUID) -> Project:
    """Authorize read access to a project."""

    project = session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError()
    ensure_project_access(session, user, project, "read")
    return project


def _require_project_write(session: Session, user: User, project_id: UUID) -> Project:
    """Authorize a state-changing operation on a project.

    Read access is not sufficient: a VIEWER must not create tests, executions,
    findings, evidence, or reports, nor modify or delete them. Naming the
    operation keeps the mutation explicit at each call site.
    """

    project = session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError()
    ensure_project_access(session, user, project, "update")
    return project


def _require_project_test(session: Session, project_id: UUID, test_id: UUID) -> None:
    """Ensure a security test belongs to the given project."""

    test = session.get(SecurityTest, test_id)
    if test is None or test.project_id != project_id:
        raise AssessmentNotFoundError()


def _require_project_target(session: Session, project_id: UUID, target_id: UUID) -> Target:
    """Ensure a target belongs to the given project and is usable.

    Targets are a separate resource from projects, so an execution can name one
    that lives in a different project. Without this check the execution engine
    would resolve that target's stored credentials and send attacker-chosen
    prompts to another tenant's model endpoint.

    Returns the target so callers can validate the test/target pairing without
    a second lookup.
    """

    target = session.get(Target, target_id)
    if target is None or target.project_id != project_id:
        raise AssessmentNotFoundError()
    return target


def validate_execution_binding(
    test: SecurityTest | None,
    target: Target | None,
) -> None:
    """Validate that a security test can actually be run against a target.

    Ownership is checked separately. This covers the pairing itself: the
    provider must match, the target must be active, and the target must
    advertise every capability the test requires. Failing these at creation
    time avoids a run that is guaranteed to fail or, worse, to reach the wrong
    provider.
    """

    if test is None or target is None:
        return

    if test.provider and test.provider != target.provider.value:
        raise ExecutionBindingError(
            f"test provider {test.provider!r} does not match target provider "
            f"{target.provider.value!r}"
        )

    if target.status != TargetStatus.ACTIVE:
        raise ExecutionBindingError(
            f"target is {target.status.value!r}; reactivate it before running tests"
        )

    required = set(test.required_capabilities or ())
    available = set(target.capabilities or ())
    missing = sorted(required - available)
    if missing:
        raise ExecutionBindingError(
            f"target does not advertise required capabilit"
            f"{'y' if len(missing) == 1 else 'ies'}: {', '.join(missing)}"
        )


def create_security_test(
    session: Session,
    project_id: UUID,
    payload: SecurityTestCreate,
    user: User,
) -> SecurityTest:
    _require_project_write(session, user, project_id)
    test = SecurityTest(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        provider=payload.provider,
        required_capabilities=payload.required_capabilities,
        config=payload.config,
    )
    session.add(test)
    session.commit()
    session.refresh(test)
    record_audit_event(
        session,
        actor_id=user.id,
        action="security_test.created",
        resource_type="security_test",
        resource_id=str(test.id),
        event_metadata={"project_id": str(project_id)},
    )
    return test


def get_security_test(session: Session, test_id: UUID, user: User) -> SecurityTest:
    test = session.get(SecurityTest, test_id)
    if test is None:
        raise AssessmentNotFoundError()
    _require_project(session, user, test.project_id)
    return test


def list_security_tests(session: Session, project_id: UUID, user: User) -> list[SecurityTest]:
    _require_project(session, user, project_id)
    return list(
        session.scalars(
            select(SecurityTest)
            .where(SecurityTest.project_id == project_id)
            .order_by(SecurityTest.created_at, SecurityTest.id)
        ).all()
    )


def update_security_test(
    session: Session,
    test_id: UUID,
    payload: SecurityTestUpdate,
    user: User,
) -> SecurityTest:
    test = get_security_test(session, test_id, user)
    _require_project_write(session, user, test.project_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(test, field, value)
    session.commit()
    session.refresh(test)
    return test


def delete_security_test(session: Session, test_id: UUID, user: User) -> bool:
    test = get_security_test(session, test_id, user)
    _require_project_write(session, user, test.project_id)
    session.delete(test)
    session.commit()
    record_audit_event(
        session,
        actor_id=user.id,
        action="security_test.deleted",
        resource_type="security_test",
        resource_id=str(test_id),
        event_metadata={"project_id": str(test.project_id)},
    )
    return True


def create_execution(
    session: Session,
    project_id: UUID,
    payload: ExecutionCreate,
    user: User,
) -> Execution:
    _require_project_write(session, user, project_id)

    test: SecurityTest | None = None
    if payload.test_id is not None:
        test = session.get(SecurityTest, payload.test_id)
        if test is None or test.project_id != project_id:
            raise AssessmentNotFoundError()

    target: Target | None = None
    if payload.target_id is not None:
        target = _require_project_target(session, project_id, payload.target_id)

    # Provider, target status, and capabilities are checked together so an
    # execution cannot be created against a pairing that cannot run.
    validate_execution_binding(test, target)

    execution = Execution(
        project_id=project_id,
        test_id=payload.test_id,
        target_id=payload.target_id,
        status=ExecutionStatus.PENDING,
        created_by=user.id,
    )
    session.add(execution)
    session.commit()
    session.refresh(execution)
    record_audit_event(
        session,
        actor_id=user.id,
        action="execution.created",
        resource_type="execution",
        resource_id=str(execution.id),
        event_metadata={"project_id": str(project_id)},
    )
    return execution


def get_execution(session: Session, execution_id: UUID, user: User) -> Execution:
    execution = session.get(Execution, execution_id)
    if execution is None:
        raise AssessmentNotFoundError()
    _require_project(session, user, execution.project_id)
    return execution


def list_executions(session: Session, project_id: UUID, user: User) -> list[Execution]:
    _require_project(session, user, project_id)
    return list(
        session.scalars(
            select(Execution)
            .where(Execution.project_id == project_id)
            .order_by(Execution.created_at, Execution.id)
        ).all()
    )


def create_finding(session: Session, payload: FindingCreate, user: User) -> Finding:
    execution = get_execution(session, payload.execution_id, user)
    _require_project_write(session, user, execution.project_id)
    finding = Finding(
        execution_id=execution.id,
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        details=payload.details,
    )
    # Apply automatic severity when the caller did not supply an explicit one.
    if finding.severity is None:
        finding.severity = compute_automatic_severity(finding)
    session.add(finding)
    session.commit()
    session.refresh(finding)
    return finding


def list_findings(session: Session, execution_id: UUID, user: User) -> list[Finding]:
    execution = get_execution(session, execution_id, user)
    return list(
        session.scalars(
            select(Finding).where(Finding.execution_id == execution.id).order_by(Finding.created_at)
        ).all()
    )


def update_finding(
    session: Session,
    finding_id: UUID,
    payload: FindingUpdate,
    user: User,
) -> Finding:
    finding = session.get(Finding, finding_id)
    if finding is None:
        raise AssessmentNotFoundError()
    execution = get_execution(session, finding.execution_id, user)
    _require_project_write(session, user, execution.project_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(finding, field, value)
    session.commit()
    session.refresh(finding)
    return finding


def create_evidence(session: Session, payload: EvidenceCreate, user: User) -> Evidence:
    finding = session.get(Finding, payload.finding_id)
    if finding is None:
        raise AssessmentNotFoundError()
    execution = get_execution(session, finding.execution_id, user)
    _require_project_write(session, user, execution.project_id)
    update_finding(
        session,
        payload.finding_id,
        FindingUpdate(status=FindingStatus.IN_PROGRESS),
        user,
    )
    evidence = Evidence(
        finding_id=payload.finding_id,
        kind=payload.kind,
        description=payload.description,
        content=payload.content,
    )
    session.add(evidence)
    session.commit()
    session.refresh(evidence)
    return evidence


def list_evidence(session: Session, finding_id: UUID, user: User) -> list[Evidence]:
    finding = session.get(Finding, finding_id)
    if finding is None:
        raise AssessmentNotFoundError()
    get_execution(session, finding.execution_id, user)
    return list(
        session.scalars(
            select(Evidence).where(Evidence.finding_id == finding_id).order_by(Evidence.created_at)
        ).all()
    )


def create_report(
    session: Session,
    project_id: UUID,
    payload: ReportCreate,
    user: User,
) -> Report:
    _require_project_write(session, user, project_id)
    report = Report(
        project_id=project_id,
        title=payload.title,
        format=payload.format,
        path="",
        created_by=user.id,
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    record_audit_event(
        session,
        actor_id=user.id,
        action="report.created",
        resource_type="report",
        resource_id=str(report.id),
        event_metadata={"project_id": str(project_id), "format": payload.format},
    )
    return report


def list_reports(session: Session, project_id: UUID, user: User) -> list[Report]:
    _require_project(session, user, project_id)
    return list(
        session.scalars(
            select(Report).where(Report.project_id == project_id).order_by(Report.created_at)
        ).all()
    )
