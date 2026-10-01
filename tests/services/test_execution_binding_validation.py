"""Execution binding validation beyond project ownership.

An execution names a test and a target. Beyond both belonging to the project,
the pair must actually be runnable:

- the test's provider must match the target's provider, or the adapter would
  be handed a target it does not support;
- the target must be active, since an inactive target is deliberately parked;
- the target must advertise every capability the test requires.

These are validated together in one function so the API path and the engine
cannot drift apart.
"""

from uuid import uuid4

import pytest
from app.api.errors import ExecutionBindingError
from app.db.session import create_session_factory
from app.models.target import Target, TargetProvider, TargetStatus
from app.models.test import SecurityTest
from app.models.user import User
from app.schemas import (
    ExecutionCreate,
    ProjectCreate,
    SecurityTestCreate,
    TargetCreate,
    TargetUpdate,
    UserCreate,
)
from app.services.assessments import create_execution, create_security_test
from app.services.auth import register_user
from app.services.projects import create_project
from app.services.targets import create_target, update_target
from sqlalchemy.orm import Session

PASSWORD = "a-very-strong-password"


def _session() -> Session:
    return create_session_factory()()


def _project(session: Session, owner: User):
    return create_project(session, ProjectCreate(name=f"Bind {uuid4()}"), owner_id=owner.id)


def _test(
    session: Session,
    project,
    owner: User,
    *,
    provider: str = "openai_compatible",
    required_capabilities: list[str] | None = None,
) -> SecurityTest:
    return create_security_test(
        session,
        project.id,
        SecurityTestCreate(
            name="Case",
            provider=provider,
            required_capabilities=required_capabilities or [],
            config={"prompts": [{"role": "user", "content": "hi"}]},
        ),
        owner,
    )


def _target(
    session: Session,
    project,
    owner: User,
    *,
    provider: TargetProvider = TargetProvider.OPENAI_COMPATIBLE,
    capabilities: list[str] | None = None,
    status: TargetStatus = TargetStatus.ACTIVE,
) -> Target:
    return create_target(
        session,
        TargetCreate(
            project_id=project.id,
            name=f"Target {uuid4()}",
            provider=provider,
            endpoint=(
                "http://aegis-ollama:11434"
                if provider == TargetProvider.OLLAMA
                else "https://model.example.com/v1"
            ),
            model="test-model" if provider != TargetProvider.CUSTOM_REST else None,
            capabilities=capabilities or [],
            status=status,
            authorization_attestation=True,
        ),
        project_id=project.id,
        user=owner,
    )


def _owner(session: Session) -> User:
    return register_user(
        session, UserCreate(email=f"bind-{uuid4()}@example.com", password=PASSWORD)
    )


def test_provider_mismatch_is_rejected() -> None:
    """A test for ollama must not run against an openai_compatible target."""

    session = _session()
    owner = _owner(session)
    project = _project(session, owner)
    try:
        test = _test(session, project, owner, provider="ollama")
        target = _target(session, project, owner, provider=TargetProvider.OPENAI_COMPATIBLE)

        with pytest.raises(ExecutionBindingError):
            create_execution(
                session,
                project.id,
                ExecutionCreate(test_id=test.id, target_id=target.id),
                owner,
            )
    finally:
        session.delete(project)
        session.commit()
        session.close()


def test_matching_provider_is_accepted() -> None:
    session = _session()
    owner = _owner(session)
    project = _project(session, owner)
    try:
        test = _test(session, project, owner, provider="openai_compatible")
        target = _target(session, project, owner, provider=TargetProvider.OPENAI_COMPATIBLE)

        execution = create_execution(
            session, project.id, ExecutionCreate(test_id=test.id, target_id=target.id), owner
        )
        assert execution.target_id == target.id
    finally:
        session.delete(project)
        session.commit()
        session.close()


def test_inactive_target_is_rejected() -> None:
    session = _session()
    owner = _owner(session)
    project = _project(session, owner)
    try:
        test = _test(session, project, owner)
        target = _target(session, project, owner, status=TargetStatus.INACTIVE)

        with pytest.raises(ExecutionBindingError):
            create_execution(
                session, project.id, ExecutionCreate(test_id=test.id, target_id=target.id), owner
            )
    finally:
        session.delete(project)
        session.commit()
        session.close()


def test_reactivated_target_is_accepted() -> None:
    """Deactivation is reversible; reactivation must unblock the target."""

    session = _session()
    owner = _owner(session)
    project = _project(session, owner)
    try:
        test = _test(session, project, owner)
        target = _target(session, project, owner, status=TargetStatus.INACTIVE)

        with pytest.raises(ExecutionBindingError):
            create_execution(
                session, project.id, ExecutionCreate(test_id=test.id, target_id=target.id), owner
            )

        update_target(session, target.id, TargetUpdate(status=TargetStatus.ACTIVE), owner)

        execution = create_execution(
            session, project.id, ExecutionCreate(test_id=test.id, target_id=target.id), owner
        )
        assert execution.target_id == target.id
    finally:
        session.delete(project)
        session.commit()
        session.close()


def test_missing_capability_is_rejected() -> None:
    session = _session()
    owner = _owner(session)
    project = _project(session, owner)
    try:
        test = _test(session, project, owner, required_capabilities=["chat", "vision"])
        target = _target(session, project, owner, capabilities=["chat"])

        with pytest.raises(ExecutionBindingError):
            create_execution(
                session, project.id, ExecutionCreate(test_id=test.id, target_id=target.id), owner
            )
    finally:
        session.delete(project)
        session.commit()
        session.close()


def test_satisfied_capabilities_are_accepted() -> None:
    session = _session()
    owner = _owner(session)
    project = _project(session, owner)
    try:
        test = _test(session, project, owner, required_capabilities=["chat"])
        target = _target(session, project, owner, capabilities=["chat", "tools"])

        execution = create_execution(
            session, project.id, ExecutionCreate(test_id=test.id, target_id=target.id), owner
        )
        assert execution.target_id == target.id
    finally:
        session.delete(project)
        session.commit()
        session.close()


def test_test_without_required_capabilities_accepts_any_target() -> None:
    """An empty requirement list imposes no constraint."""

    session = _session()
    owner = _owner(session)
    project = _project(session, owner)
    try:
        test = _test(session, project, owner, required_capabilities=[])
        target = _target(session, project, owner, capabilities=[])

        execution = create_execution(
            session, project.id, ExecutionCreate(test_id=test.id, target_id=target.id), owner
        )
        assert execution.target_id == target.id
    finally:
        session.delete(project)
        session.commit()
        session.close()


def test_null_target_still_allowed() -> None:
    """A target remains optional at the API level; the engine fails cleanly."""

    session = _session()
    owner = _owner(session)
    project = _project(session, owner)
    try:
        test = _test(session, project, owner)
        execution = create_execution(session, project.id, ExecutionCreate(test_id=test.id), owner)
        assert execution.target_id is None
    finally:
        session.delete(project)
        session.commit()
        session.close()
