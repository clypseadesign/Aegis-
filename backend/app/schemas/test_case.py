"""Test case schema for AegisAI.

Defines the YAML/JSON structure for seeded security test case files,
including single-turn and multi-turn conversation definitions, grading
configuration, and expected safe behavior documentation.
"""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TestCaseCategory(StrEnum):
    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK = "jailbreak"
    PRIVACY_LEAKAGE = "privacy_data_leakage"
    RAG_ATTACK = "rag_attack"
    AGENT_TOOL_USE = "agent_tool_use"


class GradingMethod(StrEnum):
    KEYWORD = "keyword"
    REGEX = "regex"
    JUDGE_MODEL = "judge_model"


class TestCaseMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1, max_length=1_000_000)


class JudgeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=10_000)
    pass_indicator: str | None = Field(default=None, min_length=1, max_length=500)
    fail_indicator: str | None = Field(default=None, min_length=1, max_length=500)
    inconclusive_indicator: str | None = Field(default=None, min_length=1, max_length=500)


class GradingConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    method: GradingMethod = GradingMethod.KEYWORD
    patterns: list[str] = Field(default_factory=list, max_length=100)
    regex_patterns: list[str] = Field(default_factory=list, max_length=50)
    case_insensitive: bool = True
    min_matches: int = Field(default=1, ge=1, le=100)
    severity: str = Field(default="medium", min_length=1, max_length=20)
    title: str = Field(
        default="Potential security issue detected",
        min_length=1,
        max_length=200,
    )
    judge: JudgeConfig | None = None


class TestCaseTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[TestCaseMessage] = Field(min_length=1, max_length=100)


class TestCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    category: TestCaseCategory
    provider: str = Field(min_length=1, max_length=100)
    required_capabilities: list[str] = Field(default_factory=list, max_length=50)
    system_prompt: str | None = Field(default=None, max_length=1_000_000)
    prompts: list[TestCaseMessage] = Field(default_factory=list, max_length=100)
    turns: list[TestCaseTurn] = Field(default_factory=list, max_length=20)
    expected_safe_behavior: str = Field(min_length=1, max_length=2000)
    grading: GradingConfig = Field(default_factory=GradingConfig)
    max_retries: int = Field(default=0, ge=0, le=10)
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=600.0)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=100_000)
    stop: list[str] | None = Field(default=None, max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=50)

    def to_config(self) -> dict[str, Any]:
        config: dict[str, Any] = {}
        if self.system_prompt is not None:
            config["system_prompt"] = self.system_prompt
        if self.prompts:
            config["prompts"] = [msg.model_dump() for msg in self.prompts]
        if self.turns:
            config["turns"] = [
                {"messages": [msg.model_dump() for msg in turn.messages]} for turn in self.turns
            ]
        config["grading"] = self.grading.model_dump()
        config["max_retries"] = self.max_retries
        config["timeout_seconds"] = self.timeout_seconds
        if self.temperature is not None:
            config["temperature"] = self.temperature
        if self.max_tokens is not None:
            config["max_tokens"] = self.max_tokens
        if self.stop is not None:
            config["stop"] = self.stop
        return config


__all__ = [
    "GradingConfig",
    "GradingMethod",
    "JudgeConfig",
    "TestCase",
    "TestCaseCategory",
    "TestCaseMessage",
    "TestCaseTurn",
]
