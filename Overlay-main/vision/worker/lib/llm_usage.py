"""LLM usage tracking for job-level cost aggregation.

Uses contextvars to maintain per-job token tracking, similar to trace context.
Each job execution gets its own isolated usage tracker.

Usage:
    # At job start
    usage = start_tracking()

    # During LLM calls (called automatically by _llm_extract helpers)
    track_usage("gemini-2.5-flash", response.usage_metadata)

    # At job end
    final_usage = stop_tracking()
    llm_usage_dict = final_usage.to_event_dict()  # For job event
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from pydantic import BaseModel, Field

# Cost per 1M tokens by model
LLM_COST_TABLE: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50, "cached": 0.03},
    "gemini-3-flash": {"input": 0.50, "output": 3.00, "cached": 0.05},
    "gemini-3-pro-preview": {"input": 2.00, "output": 12.00, "cached": 0.20},
}


class ModelUsage(BaseModel):
    """Token usage for a single model."""

    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cached_tokens: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert to camelCase dict for JSON serialization."""
        return {
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "thinkingTokens": self.thinking_tokens,
            "cachedTokens": self.cached_tokens,
        }


class LLMUsage(BaseModel):
    """Accumulated LLM usage for a single job execution."""

    usage_by_model: dict[str, ModelUsage] = Field(default_factory=dict)

    def track(self, model: str, usage_metadata: Any) -> None:
        """Track token usage from a Gemini response's usage_metadata.

        Args:
            model: Model name (e.g., "gemini-2.5-flash")
            usage_metadata: The usage_metadata from a Gemini response
        """
        if usage_metadata is None:
            return

        if model not in self.usage_by_model:
            self.usage_by_model[model] = ModelUsage()

        usage = self.usage_by_model[model]
        usage.input_tokens += getattr(usage_metadata, "prompt_token_count", 0) or 0
        usage.output_tokens += getattr(usage_metadata, "candidates_token_count", 0) or 0
        usage.thinking_tokens += getattr(usage_metadata, "thoughts_token_count", 0) or 0
        usage.cached_tokens += getattr(usage_metadata, "cached_content_token_count", 0) or 0

    def calculate_cost(self, cost_table: dict[str, dict[str, float]] | None = None) -> float:
        """Calculate total cost in USD.

        Args:
            cost_table: Optional custom cost table. Defaults to LLM_COST_TABLE.

        Returns:
            Total cost in USD.
        """
        if cost_table is None:
            cost_table = LLM_COST_TABLE

        total = 0.0
        for model, usage in self.usage_by_model.items():
            model_costs = cost_table.get(model, {"input": 0, "output": 0, "cached": 0})

            # Cached tokens are billed at cached rate, remaining input at full rate
            cached = usage.cached_tokens
            non_cached_input = usage.input_tokens - cached

            cached_cost = (cached / 1_000_000) * model_costs.get("cached", 0)
            input_cost = (non_cached_input / 1_000_000) * model_costs.get("input", 0)

            # Thinking tokens billed at output rate
            output_cost = (
                (usage.output_tokens + usage.thinking_tokens) / 1_000_000
            ) * model_costs.get("output", 0)

            total += input_cost + cached_cost + output_cost

        return total

    def to_event_dict(self) -> dict[str, Any]:
        """Convert to dict format for job event llmUsage field.

        Returns:
            Dict matching Option A format:
            {
                "models": {
                    "gemini-3-pro-preview": {
                        "inputTokens": 50000,
                        "outputTokens": 1200,
                        "thinkingTokens": 500,
                        "cachedTokens": 0
                    },
                    ...
                },
                "totalCostUsd": 0.0234
            }
        """
        return {
            "models": {model: usage.to_dict() for model, usage in self.usage_by_model.items()},
            "totalCostUsd": round(self.calculate_cost(), 6),
        }

    def is_empty(self) -> bool:
        """Check if any usage has been tracked."""
        return len(self.usage_by_model) == 0


# Context variable for current job's usage
_current_usage: ContextVar[LLMUsage | None] = ContextVar("llm_usage", default=None)


def start_tracking() -> LLMUsage:
    """Start tracking LLM usage for the current job.

    Returns:
        The new LLMUsage instance being tracked.
    """
    usage = LLMUsage()
    _current_usage.set(usage)
    return usage


def get_current_usage() -> LLMUsage | None:
    """Get the current job's LLM usage tracker.

    Returns:
        The current LLMUsage instance, or None if not tracking.
    """
    return _current_usage.get()


def track_usage(model: str, usage_metadata: Any) -> None:
    """Track usage from a Gemini response for the current job.

    Args:
        model: Model name (e.g., "gemini-2.5-flash")
        usage_metadata: The usage_metadata from a Gemini response

    Note:
        Does nothing if tracking hasn't been started.
    """
    usage = _current_usage.get()
    if usage is not None:
        usage.track(model, usage_metadata)


def stop_tracking() -> LLMUsage | None:
    """Stop tracking and return the accumulated usage.

    Returns:
        The accumulated LLMUsage, or None if tracking wasn't active.
    """
    usage = _current_usage.get()
    _current_usage.set(None)
    return usage
