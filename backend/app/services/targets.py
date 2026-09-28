"""Target service operations for AegisAI."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import PermissionDeniedError, TargetNotFoundError
from app.models.project import Project
from app.models.target import Target
from app.models.user import User, UserRole
from app.schemas import TargetCreate, TargetUpdate
from app.services.audit import record_audit_event
from app.services.projects import get_project_for_user

ADMIN_ROLES = {UserRole.ADMIN, UserRole.SUPER_ADMIN}


def get_target_project(
    session: Session,
    target: Target,
) -> Project:
    """Return the project containing a target."""

    project = session.get(Project, target.project_id)
    if project is None:
        raise TargetNotFoundError()
    return project


def ensure_target_access(
    session: Session,
    user: User,
    target: Target,
    operation: str,
) -> None:
    """Authorize target access and record denied attempts."""

    project = get_target_project(session, target)
    is_admin = user.role in ADMIN_ROLES
    is_owner = project.owner_id == user.id

    if not is_admin and not is_owner:
        record_audit_event(
            session,
            actor_id=user.id,
            action="target.access_denied",
            resource_type="target",
            resource_id=str(target.id),
            event_metadata={"operation": operation},
        )
        raise PermissionDeniedError()

    if operation in {"update", "delete"} and user.role == UserRole.VIEWER:
        record_audit_event(
            session,
            actor_id=user.id,
            action="target.access_denied",
            resource_type="target",
            resource_id=str(target.id),
            event_metadata={"operation": operation},
        )
        raise PermissionDeniedError()


def create_target(
    session: Session,
    payload: TargetCreate,
    project_id: UUID,
    user: User,
) -> Target:
    """Create and persist a target in an authorized project."""

    project = get_project_for_user(session, project_id, user, allow_mutation=False)
    target = Target(
        project_id=project.id,
        name=payload.name,
        description=payload.description,
        provider=payload.provider,
        endpoint=payload.endpoint,
        model=payload.model,
        capabilities=payload.capabilities,
        timeout_seconds=payload.timeout_seconds,
        rate_limit_per_minute=payload.rate_limit_per_minute,
        status=payload.status,
    )

    session.add(target)
    session.commit()
    session.refresh(target)

    return target


def get_target(
    session: Session,
    target_id: UUID,
) -> Target | None:
    """Return a target by ID, or None when it does not exist."""

    return session.get(Target, target_id)


def get_target_for_user(
    session: Session,
    target_id: UUID,
    user: User,
    *,
    allow_mutation: bool = False,
) -> Target:
    """Return an authorized target or raise a standardized error."""

    target = get_target(session, target_id)

    if target is None:
        raise TargetNotFoundError()

    ensure_target_access(session, user, target, "read" if not allow_mutation else "update")

    return target


def list_targets_for_user(
    session: Session,
    user: User,
) -> list[Target]:
    """Return targets visible to a user, filtered by project ownership unless administrative."""

    statement = select(Target).join(Project)

    if user.role not in ADMIN_ROLES:
        statement = statement.where(Project.owner_id == user.id)

    statement = statement.order_by(Target.created_at, Target.id)
    return list(session.scalars(statement).all())


def update_target(
    session: Session,
    target_id: UUID,
    payload: TargetUpdate,
    user: User,
) -> Target | None:
    """Update an existing target and return it, or None if absent."""

    target = get_target(session, target_id)

    if target is None:
        return None

    ensure_target_access(session, user, target, "update")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(target, field, value)

    session.commit()
    session.refresh(target)

    return target


def delete_target(
    session: Session,
    target_id: UUID,
    user: User,
) -> bool:
    """Delete an authorized target and return whether it existed."""

    target = get_target(session, target_id)

    if target is None:
        return False

    ensure_target_access(session, user, target, "delete")

    session.delete(target)
    session.commit()

    return True
