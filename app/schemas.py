"""Define validated contracts for HTTP questions and model-generated agent decisions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Reject unknown fields instead of silently accepting malformed model output."""

    model_config = ConfigDict(extra="forbid")


class QueryRequest(StrictModel):
    """Validate question length, session ID, Top-K, and optional document scope."""

    query: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    top_k: int = Field(4, ge=1, le=8)
    document_ids: list[str] = Field(default_factory=list, max_length=50)


class Route(StrictModel):
    """Carry resolved question intent and the router's retrieval/tool decisions."""

    intent: Literal["direct", "document", "tool", "multi_step", "follow_up"]
    needs_retrieval: bool
    needs_tools: bool
    standalone_query: str = Field(min_length=1, max_length=4000)
    reason: str = Field(max_length=600)


class Plan(StrictModel):
    """Describe bounded execution steps, a search query, and success criteria."""

    steps: list[str] = Field(min_length=1, max_length=6)
    retrieval_query: str = Field(max_length=4000)
    success_criteria: str = Field(max_length=1000)


class ToolCall(StrictModel):
    """Represent one allowed tool name, string arguments, and selection reason."""

    name: Literal["calculator", "current_time", "date_difference"]
    arguments: dict[str, str] = Field(default_factory=dict)
    reason: str = Field(max_length=600)


class ToolSelection(StrictModel):
    """Bound a tool agent's proposed work to at most three allowlisted calls."""

    calls: list[ToolCall] = Field(default_factory=list, max_length=3)
    reason: str = Field(max_length=600)


class Critique(StrictModel):
    """Carry a critic verdict and actionable feedback for an optional revision."""

    approved: bool
    issues: list[str] = Field(default_factory=list, max_length=6)
    feedback: str = Field(max_length=2000)
