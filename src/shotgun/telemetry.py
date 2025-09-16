"""Phoenix AI observability setup for cloud and local deployment."""

import logging
import os

logger = logging.getLogger(__name__)


def setup_phoenix_observability() -> bool:
    """Set up Phoenix AI observability if enabled.

    Supports both local Phoenix and cloud Phoenix (Arize) configurations.

    Returns:
        True if Phoenix was successfully set up, False otherwise
    """
    # Check if Phoenix observability is enabled
    if os.getenv("PHOENIX_ENABLED", "false").lower() not in ("true", "1", "yes"):
        logger.debug("Phoenix AI observability disabled via PHOENIX_ENABLED env var")
        return False

    try:
        # Check if using cloud Phoenix (Arize) or local Phoenix
        phoenix_collector_endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT")
        phoenix_api_key = os.getenv("PHOENIX_API_KEY")

        if not phoenix_collector_endpoint or not phoenix_api_key:
            return False

        # Cloud Phoenix setup (Arize) - following exact docs pattern
        logger.debug("Setting up cloud Phoenix AI observability")

        from openinference.instrumentation.pydantic_ai import (
            OpenInferenceSpanProcessor,
        )
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # Set up tracer provider
        tracer_provider = TracerProvider()
        trace.set_tracer_provider(tracer_provider)

        # Set up OTLP exporter for cloud Phoenix
        # Phoenix cloud expects Authorization header, not api_key
        otlp_exporter = OTLPSpanExporter(
            endpoint=phoenix_collector_endpoint,
            headers={"authorization": f"Bearer {phoenix_api_key}"},
        )

        # Add both span processors - OpenInference for semantics and BatchSpanProcessor for export
        tracer_provider.add_span_processor(OpenInferenceSpanProcessor())
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        logger.debug("Cloud Phoenix AI observability configured successfully")
        logger.debug("Endpoint: %s", phoenix_collector_endpoint)
        logger.debug("API key configured: %s", "Yes" if phoenix_api_key else "No")
        return True

    except ImportError as e:
        logger.warning("Phoenix AI not available: %s", e)
        return False
    except Exception as e:
        logger.warning("Failed to setup Phoenix AI observability: %s", e)
        return False
