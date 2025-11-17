"""
Prometheus Metrics Setup for CDC Pipeline
Full implementation in Phase 5 (User Story 3)
"""

from prometheus_client import Counter, Gauge, Histogram, start_http_server


# Prometheus Metrics (will be fully implemented in User Story 3)
# Counters
events_processed_total = Counter(
    "cdc_events_processed_total",
    "Total events processed by destination",
    ["destination", "table"],
)

errors_total = Counter(
    "cdc_errors_total", "Total errors by destination and error type", ["destination", "error_type"]
)

# Gauges
replication_lag_seconds = Gauge(
    "cdc_replication_lag_seconds", "Replication lag in seconds behind Cassandra", ["destination"]
)

events_per_second = Gauge(
    "cdc_events_per_second", "Current throughput (events/sec moving average)", ["destination"]
)

backlog_depth = Gauge(
    "cdc_backlog_depth", "Number of uncommitted events buffered", ["destination"]
)

pipeline_uptime_seconds = Counter("cdc_pipeline_uptime_seconds", "Pipeline uptime in seconds")

# Histograms
replication_duration_seconds = Histogram(
    "cdc_replication_duration_seconds",
    "Time taken to replicate an event batch",
    ["destination"],
    buckets=(0.001, 0.01, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
)


def start_metrics_server(port: int = 9090) -> None:
    """
    Start Prometheus metrics HTTP server

    Args:
        port: HTTP port to expose /metrics endpoint (default 9090)
    """
    start_http_server(port)
    print(f"Prometheus metrics server started on port {port}")


def increment_events_processed(destination: str, table: str, count: int = 1) -> None:
    """Increment events processed counter"""
    events_processed_total.labels(destination=destination, table=table).inc(count)


def increment_errors(destination: str, error_type: str, count: int = 1) -> None:
    """Increment error counter"""
    errors_total.labels(destination=destination, error_type=error_type).inc(count)


def set_replication_lag(destination: str, lag_seconds: float) -> None:
    """Set replication lag gauge"""
    replication_lag_seconds.labels(destination=destination).set(lag_seconds)


def set_throughput(destination: str, eps: float) -> None:
    """Set throughput gauge (events per second)"""
    events_per_second.labels(destination=destination).set(eps)


def set_backlog(destination: str, depth: int) -> None:
    """Set backlog depth gauge"""
    backlog_depth.labels(destination=destination).set(depth)


def observe_replication_duration(destination: str, duration_seconds: float) -> None:
    """Observe replication duration histogram"""
    replication_duration_seconds.labels(destination=destination).observe(duration_seconds)
