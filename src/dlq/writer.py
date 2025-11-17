"""
DLQ Writer
Writes failed events to JSONL files for later analysis and replay
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

from src.models.dead_letter_event import DeadLetterEvent
from src.models.event import ChangeEvent

logger = structlog.get_logger(__name__)


class DLQWriter:
    """
    Writes failed events to Dead Letter Queue

    Failed events are written as JSONL (one JSON object per line) files,
    organized by destination and date for easy analysis and replay.
    """

    def __init__(self, dlq_directory: str = "data/dlq"):
        """
        Initialize DLQ writer

        Args:
            dlq_directory: Directory to write DLQ files
        """
        self.dlq_directory = Path(dlq_directory)
        self.dlq_directory.mkdir(parents=True, exist_ok=True)

        logger.info("DLQ writer initialized", directory=str(self.dlq_directory))

    def write_event(
        self,
        event: ChangeEvent,
        destination: str,
        error_type: str,
        error_message: str,
    ) -> None:
        """
        Write failed event to DLQ

        Args:
            event: Event that failed
            destination: Destination that failed
            error_type: Type of error
            error_message: Error message
        """
        # Create dead letter event
        dlq_event = DeadLetterEvent(
            event_id=event.event_id,
            event_type=event.event_type.value,
            table_name=event.table_name,
            keyspace=event.keyspace,
            partition_key=event.partition_key,
            clustering_key=event.clustering_key,
            columns=event.columns,
            timestamp_micros=event.timestamp_micros,
            captured_at=event.captured_at.isoformat(),
            ttl_seconds=event.ttl_seconds,
            destination=destination,
            error_type=error_type,
            error_message=error_message,
            failed_at=datetime.now(timezone.utc).isoformat(),
        )

        # Generate filename: dlq_DESTINATION_DATE.jsonl
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"dlq_{destination}_{date_str}.jsonl"
        filepath = self.dlq_directory / filename

        # Append to JSONL file
        try:
            with open(filepath, "a") as f:
                json_line = json.dumps(dlq_event.to_dict())
                f.write(json_line + "\n")

            logger.warning(
                "Event written to DLQ",
                event_id=str(event.event_id),
                destination=destination,
                error_type=error_type,
                dlq_file=filename,
            )

        except Exception as e:
            logger.error("Failed to write to DLQ", error=str(e), event_id=str(event.event_id))
            # Don't raise - DLQ write failure shouldn't crash pipeline

    def get_dlq_files(self, destination: Optional[str] = None) -> list[Path]:
        """
        Get list of DLQ files

        Args:
            destination: Filter by destination (None for all)

        Returns:
            List of DLQ file paths
        """
        if destination:
            pattern = f"dlq_{destination}_*.jsonl"
        else:
            pattern = "dlq_*.jsonl"

        return sorted(self.dlq_directory.glob(pattern))

    def count_dlq_events(self, destination: Optional[str] = None) -> int:
        """
        Count total events in DLQ

        Args:
            destination: Filter by destination (None for all)

        Returns:
            Total number of events
        """
        total = 0

        for filepath in self.get_dlq_files(destination):
            with open(filepath) as f:
                total += sum(1 for _ in f)

        return total
