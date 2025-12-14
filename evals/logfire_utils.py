"""
Logfire configuration and tracing utilities for evaluation runs.

Provides mandatory Logfire setup with fail-fast behavior.
Every evaluation run must be instrumented with Logfire - no fallback mode.
"""

import os
from typing import Any

import logfire
from opentelemetry import trace

from evals.models import TraceRef, build_logfire_url


class LogfireConfigurationError(Exception):
    """Raised when Logfire cannot be configured for evaluation."""


def configure_logfire_or_fail() -> None:
    """
    Configure Logfire for evaluation runs. Raises if misconfigured.

    Requires LOGFIRE_TOKEN or SHOTGUN_LOGFIRE_TOKEN environment variable.
    Raises LogfireConfigurationError if token is not found.

    This function should be called once at the start of an evaluation run.
    """
    token = os.environ.get("LOGFIRE_TOKEN") or os.environ.get("SHOTGUN_LOGFIRE_TOKEN")

    if not token:
        raise LogfireConfigurationError(
            "Logfire token not found. Set LOGFIRE_TOKEN or SHOTGUN_LOGFIRE_TOKEN "
            "environment variable. Evaluation runs require Logfire for trace capture - "
            "no fallback mode."
        )

    logfire.configure(token=token, console=False)
    logfire.instrument_pydantic_ai()


def start_case_trace(
    test_case_name: str,
    suite_name: str,
    agent_type: str,
    metadata: dict[str, Any] | None = None,
) -> TraceRef:
    """
    Set attributes on the current span for a test case execution.

    Should be called within a logfire.span() context to populate
    span attributes with test case metadata.

    Args:
        test_case_name: Unique identifier for the test case
        suite_name: Name of the evaluation suite
        agent_type: Type of agent being evaluated (e.g., "router")
        metadata: Optional additional metadata to attach to span

    Returns:
        TraceRef with trace_id, span_id, and optional Logfire URL
    """
    span = trace.get_current_span()
    ctx = span.get_span_context()

    # Set span attributes for evaluation context
    span.set_attribute("eval.test_case_name", test_case_name)
    span.set_attribute("eval.suite_name", suite_name)
    span.set_attribute("eval.agent_type", agent_type)

    if metadata:
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                span.set_attribute(f"eval.metadata.{key}", value)

    trace_id = format(ctx.trace_id, "032x")
    span_id = format(ctx.span_id, "016x")

    return TraceRef(trace_id=trace_id, span_id=span_id, url=build_logfire_url(trace_id))


def get_current_trace_ref() -> TraceRef:
    """
    Get TraceRef for the current span context.

    Returns:
        TraceRef with current trace_id, span_id, and optional Logfire URL
    """
    span = trace.get_current_span()
    ctx = span.get_span_context()

    trace_id = format(ctx.trace_id, "032x")
    span_id = format(ctx.span_id, "016x")

    return TraceRef(trace_id=trace_id, span_id=span_id, url=build_logfire_url(trace_id))
