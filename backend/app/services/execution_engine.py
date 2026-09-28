"""Execution engine for running security tests against model targets.

Manages the lifecycle of an ``Execution`` from PENDING through RUNNING to
a terminal state (SUCCEEDED, FAILED, or CANCELLED). Provides in-process
async task scheduling with retry, timeout, cancellation, and progress
tracking. Supports both single-turn and multi-turn conversation flows.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.adapters.base import BaseTargetAdapter, ModelProviderError
from app.adapters.registry import create_model_adapter
from app.db.session import create_session_factory
from app.models.execution import Execution, ExecutionResult, ExecutionStatus
from app.models.execution_step import ExecutionStep
from app.models.finding import Finding
from app.models.model import ModelMessage, ModelRequest, ModelResponse
from app.models.project import Project
from app.models.target import Target
from app.models.test import SecurityTest
from app.security.secrets import SecretStore, get_secret_store
from app.services.audit import record_audit_event
from app.services.evidence import persist_execution_evidence
from app.services.finding_classifier import (
    classify_response,
    determine_execution_result,
)

_logger = logging.getLogger("aegis.execution")


class ExecutionError(Exception):
    """Raised when an execution cannot be started or completed."""


class ExecutionEngine:
    """In-process async execution engine.

    Schedules executions as ``asyncio`` tasks within the running event loop.
    Each task creates its own database session, runs the security test
    against the target via the appropriate model adapter, classifies the
    response for findings, persists evidence, and transitions the execution
    to a terminal state.
    """

    def __init__(
        self,
        *,
        store: SecretStore | None = None,
        adapter_factory: Callable[..., BaseTargetAdapter] | None = None,
        judge_factory: Callable[..., BaseTargetAdapter] | None = None,
    ) -> None:
        self._store = store or get_secret_store()
        self._adapter_factory = adapter_factory
        self._judge_factory = judge_factory
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    @property
    def store(self) -> SecretStore:
        return self._store

    def schedule(self, execution_id: UUID) -> None:
        """Schedule an execution for background processing.

        Raises ExecutionError if no task can be created (e.g. no running
        event loop). In FastAPI request handlers this is always available.
        """

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as exc:
            raise ExecutionError(
                "Cannot schedule execution outside of a running event loop."
            ) from exc

        task = loop.create_task(self._run(execution_id))
        self._tasks[execution_id] = task
        task.add_done_callback(lambda _t, eid=execution_id: self._tasks.pop(eid, None))

    def is_running(self, execution_id: UUID) -> bool:
        """Return whether an execution task is currently in progress."""

        task = self._tasks.get(execution_id)
        return task is not None and not task.done()

    def cancel(self, execution_id: UUID) -> bool:
        """Cancel a running execution. Returns True if a task was cancelled."""

        task = self._tasks.get(execution_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    async def _run(self, execution_id: UUID) -> None:
        """Run a single execution end-to-end with its own DB session."""

        session = create_session_factory()()
        try:
            await self.execute(session, execution_id)
        except asyncio.CancelledError:
            await self._record_cancelled(session, execution_id)
            raise
        finally:
            session.close()

    async def execute(self, session: Session, execution_id: UUID) -> None:
        """Load, run, classify, and persist results for a single execution."""

        execution = session.get(Execution, execution_id)
        if execution is None:
            _logger.warning("execution not found: %s", execution_id)
            return

        if execution.status != ExecutionStatus.PENDING:
            _logger.info(
                "execution %s already in %s state, skipping",
                execution_id,
                execution.status.value,
            )
            return

        project = session.get(Project, execution.project_id)
        if project is None:
            await self._record_failure(session, execution_id, "project not found")
            return

        test = None
        if execution.test_id is not None:
            test = session.get(SecurityTest, execution.test_id)
        if test is None:
            await self._record_failure(session, execution_id, "security test not found")
            return

        target = None
        if execution.target_id is not None:
            target = session.get(Target, execution.target_id)
        if target is None:
            await self._record_failure(session, execution_id, "target not found")
            return

        execution.status = ExecutionStatus.RUNNING
        execution.started_at = datetime.now(UTC)
        session.commit()

        record_audit_event(
            session,
            actor_id=execution.created_by,
            action="execution.started",
            resource_type="execution",
            resource_id=str(execution.id),
        )

        try:
            config = test.config or {}
            turns = config.get("turns", [])
            has_multi_turn = isinstance(turns, list) and len(turns) > 0

            adapter = _create_adapter(target, self._store, session, self._adapter_factory)

            if has_multi_turn:
                all_findings, judge_output = await self._run_multi_turn(
                    session, execution, test, target, adapter, turns
                )
            else:
                all_findings, judge_output = await self._run_single_turn(
                    session, execution, test, target, adapter
                )

            result = determine_execution_result(
                all_findings, test.config, judge_output=judge_output
            )
            execution.result = result

            execution.status = ExecutionStatus.SUCCEEDED
            execution.completed_at = datetime.now(UTC)
            session.commit()

            record_audit_event(
                session,
                actor_id=execution.created_by,
                action="execution.succeeded",
                resource_type="execution",
                resource_id=str(execution.id),
                event_metadata={"result": result.value},
            )

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            error_msg = str(exc) or exc.__class__.__name__
            execution.status = ExecutionStatus.FAILED
            execution.error = error_msg
            execution.completed_at = datetime.now(UTC)
            execution.result = ExecutionResult.INCONCLUSIVE
            session.commit()

            record_audit_event(
                session,
                actor_id=execution.created_by,
                action="execution.failed",
                resource_type="execution",
                resource_id=str(execution.id),
                event_metadata={"error": error_msg},
            )

    async def _run_single_turn(
        self,
        session: Session,
        execution: Execution,
        test: SecurityTest,
        target: Target,
        adapter: BaseTargetAdapter,
    ) -> tuple[list, str | None]:
        """Run a single-turn execution: one request, one response."""

        request = _build_request(test)
        response = await _execute_with_retries(adapter, target, request, test)

        findings = classify_response(response.output, test.config)

        judge_output = await self._maybe_judge(session, execution, test, target, response.output)

        step = ExecutionStep(
            execution_id=execution.id,
            turn_number=0,
            request_content=request.model_dump(),
            response_output=response.output,
            status="succeeded",
        )
        session.add(step)
        session.commit()
        session.refresh(step)

        for classified in findings:
            finding = Finding(
                execution_id=execution.id,
                title=classified.title,
                description=classified.description,
                severity=classified.severity,
                details=classified.details,
            )
            session.add(finding)
            session.commit()
            session.refresh(finding)

            persist_execution_evidence(
                session,
                finding=finding,
                request=request,
                response=response,
            )

        return findings, judge_output

    async def _run_multi_turn(
        self,
        session: Session,
        execution: Execution,
        test: SecurityTest,
        target: Target,
        adapter: BaseTargetAdapter,
        turns: list,
    ) -> tuple[list, str | None]:
        """Run a multi-turn execution: iterate through conversation turns."""

        config = test.config or {}
        all_findings: list = []
        conversation_messages: list[ModelMessage] = []
        judge_output: str | None = None

        if config.get("system_prompt"):
            conversation_messages.append(
                ModelMessage(role="system", content=config["system_prompt"])
            )

        for turn_idx, turn in enumerate(turns):
            turn_messages = _parse_turn_messages(turn, conversation_messages)

            # Carry the turn's new user messages into the running history so
            # later turns see the full conversation, not just prior replies.
            for message in turn_messages[len(conversation_messages) :]:
                conversation_messages.append(message)

            request = ModelRequest(
                messages=turn_messages,
                system_prompt=None,
                temperature=config.get("temperature"),
                max_tokens=config.get("max_tokens"),
                stop=config.get("stop"),
            )

            response = await _execute_with_retries(adapter, target, request, test)

            step = ExecutionStep(
                execution_id=execution.id,
                turn_number=turn_idx,
                request_content=request.model_dump(),
                response_output=response.output,
                status="succeeded",
            )
            session.add(step)
            session.commit()
            session.refresh(step)

            findings = classify_response(response.output, test.config)
            all_findings.extend(findings)

            for classified in findings:
                finding = Finding(
                    execution_id=execution.id,
                    title=classified.title,
                    description=classified.description,
                    severity=classified.severity,
                    details=classified.details,
                )
                session.add(finding)
                session.commit()
                session.refresh(finding)

                persist_execution_evidence(
                    session,
                    finding=finding,
                    request=request,
                    response=response,
                )

            conversation_messages.append(ModelMessage(role="assistant", content=response.output))

        judge_output = await self._maybe_judge(
            session, execution, test, target, conversation_messages[-1].content
        )

        return all_findings, judge_output

    async def _maybe_judge(
        self,
        session: Session,
        execution: Execution,
        test: SecurityTest,
        target: Target,
        response_output: str,
    ) -> str | None:
        """Optionally invoke a judge model for judge-model-based grading."""

        config = test.config or {}
        grading = config.get("grading", {}) if isinstance(config, dict) else {}
        if not isinstance(grading, dict):
            return None
        if grading.get("method") != "judge_model":
            return None
        if self._judge_factory is None:
            _logger.warning(
                "judge_model grading requested for execution %s but no "
                "judge_factory is configured; falling back to INCONCLUSIVE",
                execution.id,
            )
            return None

        judge_raw = grading.get("judge")
        judge = judge_raw if isinstance(judge_raw, dict) else {}
        judge_prompt = judge.get("prompt", "Evaluate the following response: {{response}}")
        judge_prompt = judge_prompt.replace("{{response}}", response_output)

        judge_messages = [ModelMessage(role="user", content=judge_prompt)]
        judge_request = ModelRequest(messages=judge_messages)
        judge_adapter = self._judge_factory(
            target.provider,
            credential_resolver=None,
        )

        try:
            judge_response = await _execute_with_retries(judge_adapter, target, judge_request, test)
            return judge_response.output
        except Exception as exc:
            _logger.warning(
                "judge model call failed for execution %s: %s",
                execution.id,
                exc,
            )
            return None
        finally:
            if hasattr(judge_adapter, "close"):
                await judge_adapter.close()

    async def _record_failure(
        self,
        session: Session,
        execution_id: UUID,
        message: str = "",
    ) -> None:
        """Record a terminal FAILED state for an execution that could not run."""

        execution = session.get(Execution, execution_id)
        if execution is None:
            return

        if execution.status not in (ExecutionStatus.PENDING, ExecutionStatus.RUNNING):
            return

        execution.status = ExecutionStatus.FAILED
        execution.error = message or "execution could not be started"
        execution.completed_at = datetime.now(UTC)
        execution.result = ExecutionResult.INCONCLUSIVE
        session.commit()

    async def _record_cancelled(self, session: Session, execution_id: UUID) -> None:
        """Record a terminal CANCELLED state for a cancelled execution."""

        execution = session.get(Execution, execution_id)
        if execution is None:
            return

        if execution.status in (
            ExecutionStatus.PENDING,
            ExecutionStatus.RUNNING,
        ):
            execution.status = ExecutionStatus.CANCELLED
            execution.completed_at = datetime.now(UTC)
            session.commit()

        record_audit_event(
            session,
            actor_id=execution.created_by,
            action="execution.cancelled",
            resource_type="execution",
            resource_id=str(execution_id),
        )


_engine: ExecutionEngine | None = None


def get_engine() -> ExecutionEngine:
    """Return the shared module-level execution engine (lazily created)."""

    global _engine
    if _engine is None:
        _engine = ExecutionEngine()
    return _engine


def set_engine(engine: ExecutionEngine) -> None:
    """Override the shared engine (for testing)."""

    global _engine
    _engine = engine


def start_execution(execution_id: UUID) -> None:
    """Schedule an execution for background processing."""

    get_engine().schedule(execution_id)


def cancel_execution(execution_id: UUID) -> bool:
    """Cancel a running execution. Returns True if a task was found and cancelled."""

    return get_engine().cancel(execution_id)


def is_execution_running(execution_id: UUID) -> bool:
    """Return whether an execution task is currently in progress."""

    return get_engine().is_running(execution_id)


def _build_request(test: SecurityTest) -> ModelRequest:
    """Build a ``ModelRequest`` from the security test's configuration."""

    config = test.config or {}

    prompts = config.get("prompts", [])
    messages = [ModelMessage(**msg) for msg in prompts if isinstance(msg, dict)]

    if not messages:
        messages = [ModelMessage(role="user", content="hello")]

    return ModelRequest(
        messages=messages,
        system_prompt=config.get("system_prompt"),
        temperature=config.get("temperature"),
        max_tokens=config.get("max_tokens"),
    )


def _parse_turn_messages(turn: dict | list, history: list[ModelMessage]) -> list[ModelMessage]:
    """Extract messages from a multi-turn turn definition.

    If the turn is a dict with a ``messages`` key, uses those messages.
    If it's a list, uses the items directly. The current conversation
    history is prepended so the model sees context from prior turns.
    """

    if isinstance(turn, dict):
        raw_messages = turn.get("messages", [])
    elif isinstance(turn, list):
        raw_messages = turn
    else:
        return list(history)

    turn_messages = [ModelMessage(**msg) for msg in raw_messages if isinstance(msg, dict)]

    return list(history) + turn_messages


def _create_adapter(
    target: Target,
    store: SecretStore,
    session: Session,
    adapter_factory: Callable[..., BaseTargetAdapter] | None,
) -> BaseTargetAdapter:
    """Create a model adapter for the target, respecting SSRF/network policy.

    The adapter always uses the project credential store and the validated
    network policy — there is no bypass path for execution.
    """

    from app.adapters.resolver import create_credential_resolver

    credential_resolver = create_credential_resolver(session, store)

    if adapter_factory is not None:
        return adapter_factory(
            target.provider,
            credential_resolver=credential_resolver,
        )

    return create_model_adapter(
        target.provider,
        credential_resolver=credential_resolver,
    )


async def _execute_with_retries(
    adapter: BaseTargetAdapter,
    target: Target,
    request: ModelRequest,
    test: SecurityTest,
) -> ModelResponse:
    """Execute a model request with configurable retries and timeout.

    Retries are limited to transient provider errors and timeouts.
    """

    config = test.config or {}
    max_retries = int(config.get("max_retries", 0))
    timeout = float(config.get("timeout_seconds", target.timeout_seconds))

    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return await asyncio.wait_for(adapter.generate(target, request), timeout=timeout)
        except (ModelProviderError, TimeoutError) as exc:
            last_error = exc
            if attempt < max_retries:
                backoff = 2**attempt
                _logger.info(
                    "execution attempt %d failed, retrying in %ds",
                    attempt + 1,
                    backoff,
                )
                await asyncio.sleep(backoff)
            continue

    if last_error is not None:
        raise last_error
    raise ModelProviderError("execution failed with no error details")
