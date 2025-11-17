"""
OpenTelemetry Tracing Setup for CDC Pipeline
Full implementation in Phase 5 (User Story 3)
"""

from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# Global tracer instance
tracer: Optional[trace.Tracer] = None


def init_tracing(
    service_name: str = "cdc-pipeline",
    enable_console_export: bool = False,
) -> trace.Tracer:
    """
    Initialize OpenTelemetry tracing (basic setup for Phase 2)

    Args:
        service_name: Name of the service for trace identification
        enable_console_export: Whether to export traces to console (dev mode)

    Returns:
        Configured Tracer instance

    Note:
        Full implementation with OTLP exporters, sampling, and span enrichment
        will be added in Phase 5 (User Story 3)
    """
    global tracer

    # Create resource with service name
    resource = Resource(attributes={SERVICE_NAME: service_name})

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add console exporter for development (optional)
    if enable_console_export:
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    # Get tracer instance
    tracer = trace.get_tracer(__name__)

    return tracer


def get_tracer() -> trace.Tracer:
    """
    Get the global tracer instance

    Returns:
        Tracer instance

    Raises:
        RuntimeError: If tracing has not been initialized
    """
    if tracer is None:
        raise RuntimeError("Tracing not initialized. Call init_tracing() first.")
    return tracer


def trace_replication_event(
    event_id: str,
    table_name: str,
    destination: str,
) -> trace.Span:
    """
    Create a span for replication event processing

    Args:
        event_id: Unique event identifier
        table_name: Source table name
        destination: Target destination name

    Returns:
        Active span for the replication event
    """
    if tracer is None:
        # Return a no-op span if tracing is not initialized
        return trace.get_current_span()

    span = tracer.start_span(
        "replicate_event",
        attributes={
            "event.id": event_id,
            "table.name": table_name,
            "destination": destination,
        },
    )
    return span


def trace_batch_write(
    batch_size: int,
    destination: str,
) -> trace.Span:
    """
    Create a span for batch write operations

    Args:
        batch_size: Number of events in the batch
        destination: Target destination name

    Returns:
        Active span for the batch write
    """
    if tracer is None:
        return trace.get_current_span()

    span = tracer.start_span(
        "batch_write",
        attributes={
            "batch.size": batch_size,
            "destination": destination,
        },
    )
    return span
