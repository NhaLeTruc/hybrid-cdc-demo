"""
Destination Sink Model
Tracks state and health of each destination sink
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from src.models.offset import Destination


class SinkHealth(Enum):
    """Health status of a sink"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class DestinationSink:
    """
    Represents a destination sink with its current state and health

    Attributes:
        destination: Destination type
        health: Current health status
        last_health_check: When health was last checked
        latency_ms: Last measured latency
        events_written: Total events written to this destination
        errors_count: Total errors for this destination
        last_error: Last error message
        last_error_at: When last error occurred
        is_connected: Whether sink is currently connected
        backlog_depth: Number of uncommitted events
        throughput_eps: Current throughput (events per second)
        replication_lag_seconds: Replication lag behind source
    """

    destination: Destination
    health: SinkHealth = SinkHealth.UNKNOWN
    last_health_check: Optional[datetime] = None
    latency_ms: float = 0.0
    events_written: int = 0
    errors_count: int = 0
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    is_connected: bool = False
    backlog_depth: int = 0
    throughput_eps: float = 0.0
    replication_lag_seconds: float = 0.0

    def update_health(self, is_healthy: bool, latency_ms: float) -> None:
        """
        Update health status

        Args:
            is_healthy: Whether sink is healthy
            latency_ms: Latency in milliseconds
        """
        self.last_health_check = datetime.now(timezone.utc)
        self.latency_ms = latency_ms

        if not is_healthy:
            self.health = SinkHealth.UNHEALTHY
        elif latency_ms > 1000:  # > 1 second
            self.health = SinkHealth.DEGRADED
        else:
            self.health = SinkHealth.HEALTHY

    def record_events_written(self, count: int) -> None:
        """
        Record events written

        Args:
            count: Number of events written
        """
        self.events_written += count

    def record_error(self, error_message: str) -> None:
        """
        Record an error

        Args:
            error_message: Error message
        """
        self.errors_count += 1
        self.last_error = error_message
        self.last_error_at = datetime.now(timezone.utc)
        self.health = SinkHealth.UNHEALTHY

    def update_metrics(
        self,
        backlog_depth: int,
        throughput_eps: float,
        replication_lag_seconds: float,
    ) -> None:
        """
        Update performance metrics

        Args:
            backlog_depth: Number of uncommitted events
            throughput_eps: Throughput in events per second
            replication_lag_seconds: Replication lag in seconds
        """
        self.backlog_depth = backlog_depth
        self.throughput_eps = throughput_eps
        self.replication_lag_seconds = replication_lag_seconds

    def to_dict(self) -> dict:
        """
        Convert to dictionary

        Returns:
            Dict representation
        """
        return {
            "destination": self.destination.value,
            "health": self.health.value,
            "last_health_check": (
                self.last_health_check.isoformat() if self.last_health_check else None
            ),
            "latency_ms": self.latency_ms,
            "events_written": self.events_written,
            "errors_count": self.errors_count,
            "last_error": self.last_error,
            "last_error_at": self.last_error_at.isoformat() if self.last_error_at else None,
            "is_connected": self.is_connected,
            "backlog_depth": self.backlog_depth,
            "throughput_eps": self.throughput_eps,
            "replication_lag_seconds": self.replication_lag_seconds,
        }
