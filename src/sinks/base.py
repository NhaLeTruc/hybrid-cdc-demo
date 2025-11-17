"""
Base Sink Interface
Abstract base class for all destination sinks
"""

from abc import ABC, abstractmethod
from typing import List, Optional
import structlog

from src.models.event import ChangeEvent
from src.models.offset import ReplicationOffset, Destination

logger = structlog.get_logger(__name__)


class SinkError(Exception):
    """Base exception for sink errors"""

    pass


class BaseSink(ABC):
    """
    Abstract base class for destination sinks

    All sinks must implement:
    - connect(): Establish connection to destination
    - write_batch(): Write a batch of events
    - commit_offset(): Atomically commit offset with data
    - health_check(): Verify destination is healthy
    """

    def __init__(self, destination: Destination):
        """
        Initialize sink

        Args:
            destination: Destination type for this sink
        """
        self.destination = destination
        self.is_connected = False
        self._events_written = 0
        self._errors_count = 0

        logger.info("Sink initialized", destination=destination.value)

    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to destination database

        Raises:
            SinkError: If connection fails
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close connection to destination database
        """
        pass

    @abstractmethod
    async def write_batch(self, events: List[ChangeEvent]) -> int:
        """
        Write a batch of events to the destination

        This should be idempotent - writing the same event_id multiple times
        should result in only one record.

        Args:
            events: List of ChangeEvents to write

        Returns:
            Number of events successfully written

        Raises:
            SinkError: If write fails
        """
        pass

    @abstractmethod
    async def commit_offset(self, offset: ReplicationOffset) -> None:
        """
        Atomically commit offset with data writes

        This must be called within the same transaction as write_batch
        to ensure exactly-once delivery.

        Args:
            offset: Offset to commit

        Raises:
            SinkError: If commit fails
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if destination is healthy and reachable

        Returns:
            True if healthy, False otherwise
        """
        pass

    async def ensure_connected(self) -> None:
        """
        Ensure sink is connected, reconnect if needed

        Raises:
            SinkError: If connection cannot be established
        """
        if not self.is_connected:
            logger.info("Connecting to destination", destination=self.destination.value)
            await self.connect()

    def increment_events_written(self, count: int = 1) -> None:
        """
        Increment the events written counter

        Args:
            count: Number of events to add to counter
        """
        self._events_written += count

    def increment_errors(self, count: int = 1) -> None:
        """
        Increment the error counter

        Args:
            count: Number of errors to add to counter
        """
        self._errors_count += count

    def get_stats(self) -> dict:
        """
        Get sink statistics

        Returns:
            Dict with events_written, errors_count, etc.
        """
        return {
            "destination": self.destination.value,
            "is_connected": self.is_connected,
            "events_written": self._events_written,
            "errors_count": self._errors_count,
        }

    async def __aenter__(self):
        """Async context manager entry"""
        await self.ensure_connected()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()
