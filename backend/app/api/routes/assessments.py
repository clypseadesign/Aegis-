"""Assessment (test, execution, finding, evidence, report) API routes for AegisAI."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.errors import ProjectNotFoundError
from app.db.session import get_db_session
from app.models.execution import ExecutionStatus
from app.schemas import (
    EvidenceCreate,
    EvidenceResponse,
    ExecutionCreate,
    ExecutionResponse,
    ExecutionUpdate,
    FindingCreate,
    FindingResponse,
    FindingUpdate,
    ReportComparisonResponse,
    ReportCreate,
    ReportResponse,
    SecurityTestCreate,
    SecurityTestResponse,
    SecurityTestUpdate,
    TestSeedRequest,
    TestSeedResponse,
)
from app.security.dependencies import CurrentUser
from app.services.assessments import (
    create_evidence,
    create_execution,
    create_finding,
    create_report,
    create_security_test,
    delete_security_test,
    get_execution,
    get_security_test,
    list_evidence,
    list_executions,
    list_findings,
    list_reports,
    list_security_tests,
    update_execution,
    update_finding,
    update_security_test,
)
from app.services.audit import record_audit_event
from app.services.execution_engine import (
    cancel_execution,
    start_execution,
)
from app.services.report_generation import (
    compare_reports,
    generate_report,
    get_report_download_path,
    require_project_report,
)
from app.services.seed_tests import seed_project_tests

router = APIRouter(
    prefix="/projects/{project_id}/assessments",
    tags=["assessments"],
)

DatabaseSession = Annotated[Session, Depends(get_db_session)]


def _test_response(test) -> SecurityTestResponse:
    return SecurityTestResponse.model_validate(test)


@router.post("/tests", response_model=SecurityTestResponse, status_code=status.HTTP_201_CREATED)
async def create_test_endpoint(
    project_id: UUID,
    payload: SecurityTestCreate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> SecurityTestResponse:
    return _test_response(create_security_test(session, project_id, payload, current_user))


@router.get("/tests", response_model=list[SecurityTestResponse])
async def list_tests_endpoint(
    project_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> list[SecurityTestResponse]:
    return [_test_response(t) for t in list_security_tests(session, project_id, current_user)]


@router.get("/tests/{test_id}", response_model=SecurityTestResponse)
async def get_test_endpoint(
    project_id: UUID,
    test_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> SecurityTestResponse:
    return _test_response(get_security_test(session, test_id, current_user))


@router.patch("/tests/{test_id}", response_model=SecurityTestResponse)
async def update_test_endpoint(
    project_id: UUID,
    test_id: UUID,
    payload: SecurityTestUpdate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> SecurityTestResponse:
    _ = get_security_test(session, test_id, current_user)
    return _test_response(update_security_test(session, test_id, payload, current_user))


@router.post("/tests/seed", response_model=TestSeedResponse)
async def seed_tests_endpoint(
    project_id: UUID,
    payload: TestSeedRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> TestSeedResponse:
    """Load the bundled security test library into a project.

    The YAML files under ``app/test_cases`` are static and are not imported
    automatically, so a new project has no tests until this is called. The
    operation is idempotent: tests already present in the project are skipped,
    so it is safe to call repeatedly.
    """

    report = seed_project_tests(
        session,
        project_id,
        current_user,
        categories=set(payload.category) or None,
    )
    return TestSeedResponse.from_report(report)


@router.delete("/tests/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_endpoint(
    project_id: UUID,
    test_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> None:
    delete_security_test(session, test_id, current_user)


@router.post("/executions", response_model=ExecutionResponse, status_code=status.HTTP_201_CREATED)
async def create_execution_endpoint(
    project_id: UUID,
    payload: ExecutionCreate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> ExecutionResponse:
    return ExecutionResponse.model_validate(
        create_execution(session, project_id, payload, current_user)
    )


@router.get("/executions", response_model=list[ExecutionResponse])
async def list_executions_endpoint(
    project_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> list[ExecutionResponse]:
    return [
        ExecutionResponse.model_validate(e)
        for e in list_executions(session, project_id, current_user)
    ]


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution_endpoint(
    project_id: UUID,
    execution_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> ExecutionResponse:
    """Return a single execution for status polling."""

    execution = get_execution(session, execution_id, current_user)
    if execution.project_id != project_id:
        raise ProjectNotFoundError()

    return ExecutionResponse.model_validate(execution)


@router.patch("/executions/{execution_id}", response_model=ExecutionResponse)
async def update_execution_endpoint(
    project_id: UUID,
    execution_id: UUID,
    payload: ExecutionUpdate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> ExecutionResponse:
    _ = get_execution(session, execution_id, current_user)
    return ExecutionResponse.model_validate(
        update_execution(session, execution_id, payload, current_user)
    )


@router.post(
    "/executions/{execution_id}/run",
    response_model=ExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_execution_endpoint(
    project_id: UUID,
    execution_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> ExecutionResponse:
    """Queue an execution for background processing.

    Returns 202 Accepted with the execution record. The execution transitions
    from PENDING to RUNNING asynchronously; poll GET /executions/{id} for
    status.
    """

    execution = get_execution(session, execution_id, current_user)
    if execution.project_id != project_id:
        raise ProjectNotFoundError()

    if execution.status != ExecutionStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"execution is in '{execution.status.value}' state; "
                "only PENDING executions can be started."
            ),
        )

    start_execution(execution.id)

    return ExecutionResponse.model_validate(execution)


@router.post(
    "/executions/{execution_id}/cancel",
    response_model=ExecutionResponse,
)
async def cancel_execution_endpoint(
    project_id: UUID,
    execution_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> ExecutionResponse:
    """Attempt to cancel a running or pending execution."""

    execution = get_execution(session, execution_id, current_user)
    if execution.project_id != project_id:
        raise ProjectNotFoundError()

    cancelled = cancel_execution(execution.id)

    session.refresh(execution)

    if not cancelled:
        return ExecutionResponse.model_validate(execution)

    return ExecutionResponse.model_validate(execution)


@router.post("/findings", response_model=FindingResponse, status_code=status.HTTP_201_CREATED)
async def create_finding_endpoint(
    payload: FindingCreate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> FindingResponse:
    return FindingResponse.model_validate(create_finding(session, payload, current_user))


@router.get("/executions/{execution_id}/findings", response_model=list[FindingResponse])
async def list_findings_endpoint(
    project_id: UUID,
    execution_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> list[FindingResponse]:
    return [
        FindingResponse.model_validate(f)
        for f in list_findings(session, execution_id, current_user)
    ]


@router.patch("/findings/{finding_id}", response_model=FindingResponse)
async def update_finding_endpoint(
    project_id: UUID,
    finding_id: UUID,
    payload: FindingUpdate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> FindingResponse:
    return FindingResponse.model_validate(
        update_finding(session, finding_id, payload, current_user)
    )


@router.post("/evidence", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
async def create_evidence_endpoint(
    payload: EvidenceCreate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> EvidenceResponse:
    return EvidenceResponse.model_validate(create_evidence(session, payload, current_user))


@router.get("/findings/{finding_id}/evidence", response_model=list[EvidenceResponse])
async def list_evidence_endpoint(
    project_id: UUID,
    finding_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> list[EvidenceResponse]:
    return [
        EvidenceResponse.model_validate(e) for e in list_evidence(session, finding_id, current_user)
    ]


@router.post("/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report_endpoint(
    project_id: UUID,
    payload: ReportCreate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> ReportResponse:
    return ReportResponse.model_validate(create_report(session, project_id, payload, current_user))


@router.post(
    "/reports/{report_id}/generate",
    response_model=ReportResponse,
)
async def generate_report_endpoint(
    project_id: UUID,
    report_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> ReportResponse:
    """Generate (or regenerate) a report artifact and return its updated record."""

    report = require_project_report(session, current_user, project_id, report_id)
    generate_report(session, report)
    session.refresh(report)
    record_audit_event(
        session,
        actor_id=current_user.id,
        action="report.generated",
        resource_type="report",
        resource_id=str(report.id),
        event_metadata={"project_id": str(project_id), "format": report.format},
    )
    return ReportResponse.model_validate(report)


@router.get("/reports", response_model=list[ReportResponse])
async def list_reports_endpoint(
    project_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> list[ReportResponse]:
    """List report history for a project, oldest version first."""

    return [
        ReportResponse.model_validate(r) for r in list_reports(session, project_id, current_user)
    ]


@router.get("/reports/{report_id}/download")
async def download_report_endpoint(
    project_id: UUID,
    report_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> FileResponse:
    """Download a generated report artifact.

    Report artifacts contain the full evidence set, so the response is marked
    no-store to keep them out of shared and browser caches.
    """

    require_project_report(session, current_user, project_id, report_id)
    path = get_report_download_path(session, report_id, project_id)
    record_audit_event(
        session,
        actor_id=current_user.id,
        action="report.downloaded",
        resource_type="report",
        resource_id=str(report_id),
        event_metadata={"project_id": str(project_id)},
    )
    media_type = "application/json" if path.suffix == ".json" else "text/markdown"
    return FileResponse(
        path=str(path),
        media_type=media_type,
        filename=path.name,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get(
    "/reports/{report_a_id}/compare/{report_b_id}",
    response_model=ReportComparisonResponse,
)
async def compare_reports_endpoint(
    project_id: UUID,
    report_a_id: UUID,
    report_b_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> ReportComparisonResponse:
    """Compare two report runs and return new/resolved/regressed findings."""

    # Both reports must be authorized against the same project, otherwise a
    # caller could compare their own report against another tenant's.
    require_project_report(session, current_user, project_id, report_a_id)
    require_project_report(session, current_user, project_id, report_b_id)
    record_audit_event(
        session,
        actor_id=current_user.id,
        action="report.compared",
        resource_type="report",
        resource_id=str(report_a_id),
        event_metadata={
            "project_id": str(project_id),
            "other_report_id": str(report_b_id),
        },
    )
    return ReportComparisonResponse.model_validate(
        compare_reports(session, report_a_id, report_b_id, project_id)
    )
