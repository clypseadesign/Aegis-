"""Evidence persistence helpers for AegisAI executions.

Auto-persists request/response pairs as ``Evidence`` records linked to
the finding generated during an execution.
"""

from sqlalchemy.orm import Session

from app.models.evidence import Evidence
from app.models.finding import Finding
from app.models.model import ModelRequest, ModelResponse


def persist_execution_evidence(
    session: Session,
    *,
    finding: Finding,
    request: ModelRequest,
    response: ModelResponse,
) -> list[Evidence]:
    """Persist request and response as evidence for a finding.

    Creates two evidence records: one for the model request that triggered
    the finding, and one for the model response that matched the grading
    patterns.
    """

    request_evidence = Evidence(
        finding_id=finding.id,
        kind="model_request",
        description="Prompt sent to the target model during execution.",
        content=_request_to_dict(request),
    )
    session.add(request_evidence)

    response_evidence = Evidence(
        finding_id=finding.id,
        kind="model_response",
        description="Response received from the target model during execution.",
        content=_response_to_dict(response),
    )
    session.add(response_evidence)

    session.commit()
    session.refresh(request_evidence)
    session.refresh(response_evidence)

    return [request_evidence, response_evidence]


def _request_to_dict(request: ModelRequest) -> dict:
    """Serialize a ModelRequest for evidence storage."""

    return {
        "messages": [msg.model_dump() for msg in request.messages],
        "system_prompt": request.system_prompt,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "stop": request.stop,
        "metadata": request.metadata,
    }


def _response_to_dict(response: ModelResponse) -> dict:
    """Serialize a ModelResponse for evidence storage."""

    return {
        "output": response.output,
        "finish_reason": response.finish_reason,
        "model": response.model,
        "latency_seconds": response.latency_seconds,
        "provider_request_id": response.provider_request_id,
        "usage": response.usage.model_dump() if response.usage else None,
        "metadata": response.metadata,
    }
