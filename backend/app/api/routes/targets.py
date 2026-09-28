"""Target API routes for AegisAI."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.errors import TargetNotFoundError
from app.db.session import get_db_session
from app.schemas import TargetCreate, TargetResponse, TargetUpdate
from app.security.dependencies import CurrentUser
from app.services.audit import record_audit_event
from app.services.targets import (
    create_target,
    delete_target,
    get_target_for_user,
    list_targets_for_user,
    update_target,
)

router = APIRouter(
    prefix="/targets",
    tags=["targets"],
)

DatabaseSession = Annotated[Session, Depends(get_db_session)]


@router.post(
    "",
    response_model=TargetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_target_endpoint(
    payload: TargetCreate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> TargetResponse:
    """Create a target in an authorized project."""

    target = create_target(
        session,
        payload,
        project_id=payload.project_id,
        user=current_user,
    )

    record_audit_event(
        session,
        actor_id=current_user.id,
        action="target.created",
        resource_type="target",
        resource_id=str(target.id),
        event_metadata={"project_id": str(target.project_id)},
    )

    return TargetResponse.model_validate(target)


@router.get(
    "",
    response_model=list[TargetResponse],
)
async def list_targets_endpoint(
    current_user: CurrentUser,
    session: DatabaseSession,
) -> list[TargetResponse]:
    """Return targets visible to the authenticated user."""

    targets = list_targets_for_user(session, current_user)

    return [TargetResponse.model_validate(target) for target in targets]


@router.get(
    "/{target_id}",
    response_model=TargetResponse,
)
async def get_target_endpoint(
    target_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> TargetResponse:
    """Return an authorized target by ID."""

    target = get_target_for_user(session, target_id, current_user)

    return TargetResponse.model_validate(target)


@router.patch(
    "/{target_id}",
    response_model=TargetResponse,
)
async def update_target_endpoint(
    target_id: UUID,
    payload: TargetUpdate,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> TargetResponse:
    """Update an authorized existing target."""

    target = update_target(
        session,
        target_id,
        payload,
        current_user,
    )

    if target is None:
        raise TargetNotFoundError()

    record_audit_event(
        session,
        actor_id=current_user.id,
        action="target.updated",
        resource_type="target",
        resource_id=str(target.id),
        event_metadata={
            "changed_fields": sorted(payload.model_dump(exclude_unset=True)),
            "project_id": str(target.project_id),
        },
    )

    return TargetResponse.model_validate(target)


@router.delete(
    "/{target_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_target_endpoint(
    target_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> None:
    """Delete an authorized existing target."""

    deleted = delete_target(
        session,
        target_id,
        current_user,
    )

    if not deleted:
        raise TargetNotFoundError()

    record_audit_event(
        session,
        actor_id=current_user.id,
        action="target.deleted",
        resource_type="target",
        resource_id=str(target_id),
    )
