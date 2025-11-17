"""
ClickHouse Sink
Writes CDC events to ClickHouse warehouse using clickhouse-driver
"""

from typing import List, Optional

import structlog
from clickhouse_driver import Client

from src.models.event import ChangeEvent, EventType
from src.models.offset import Destination, ReplicationOffset
from src.sinks.base import BaseSink, SinkError

logger = structlog.get_logger(__name__)


class ClickHouseSink(BaseSink):
    """
    ClickHouse sink using ReplacingMergeTree for deduplication
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9000,
        database: str = "analytics",
        user: str = "default",
        password: str = "",
    ):
        """
        Initialize ClickHouse sink

        Args:
            host: ClickHouse host
            port: ClickHouse native port (9000)
            database: Database name
            user: Username
            password: Password
        """
        super().__init__(Destination.CLICKHOUSE)
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self._client: Optional[Client] = None

    async def connect(self) -> None:
        """
        Establish connection to ClickHouse

        Raises:
            SinkError: If connection fails
        """
        try:
            self._client = Client(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
            )

            # Test connection
            self._client.execute("SELECT 1")
            self.is_connected = True
            logger.info("Connected to ClickHouse", database=self.database)

        except Exception as e:
            self.increment_errors()
            raise SinkError(f"Failed to connect to ClickHouse: {e}") from e

    async def disconnect(self) -> None:
        """Close ClickHouse connection"""
        if self._client:
            self._client.disconnect()
            self.is_connected = False
            logger.info("Disconnected from ClickHouse")

    async def write_batch(self, events: List[ChangeEvent]) -> int:
        """
        Write batch of events to ClickHouse

        Uses ReplacingMergeTree for automatic deduplication.
        ClickHouse doesn't support transactions, so we rely on ReplacingMergeTree.

        Args:
            events: List of ChangeEvents to write

        Returns:
            Number of events successfully written

        Raises:
            SinkError: If write fails
        """
        if not self._client:
            raise SinkError("Not connected to ClickHouse")

        if not events:
            return 0

        try:
            written_count = 0

            for event in events:
                table = f"{self.database}.{event.table_name}"

                if event.event_type == EventType.DELETE:
                    # ClickHouse doesn't support DELETE in standard way
                    # We'll insert a "tombstone" record with a special marker
                    # or skip deletes for analytics warehouse
                    logger.warning(
                        "DELETE events not fully supported in ClickHouse", table=event.table_name
                    )
                    continue

                else:
                    # INSERT for INSERT/UPDATE events
                    # Combine all columns
                    all_columns = {
                        **event.partition_key,
                        **event.clustering_key,
                        **event.columns,
                    }

                    # Build column names and values
                    columns = list(all_columns.keys())
                    values = [all_columns[col] for col in columns]

                    # Build INSERT query
                    query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES"

                    # Execute insert
                    self._client.execute(query, [values])

                written_count += 1

            self.increment_events_written(written_count)
            logger.info("Wrote batch to ClickHouse", count=written_count)
            return written_count

        except Exception as e:
            self.increment_errors()
            raise SinkError(f"Failed to write batch to ClickHouse: {e}") from e

    async def commit_offset(self, offset: ReplicationOffset) -> None:
        """
        Commit offset to ClickHouse offset table

        Note: ClickHouse doesn't support transactions, so offset commits
        are separate from data writes.

        Args:
            offset: Offset to commit

        Raises:
            SinkError: If commit fails
        """
        if not self._client:
            raise SinkError("Not connected to ClickHouse")

        try:
            # Insert offset (ReplacingMergeTree will handle deduplication)
            query = """
                INSERT INTO analytics.cdc_offsets (
                    offset_id, table_name, keyspace, partition_id, destination,
                    commitlog_file, commitlog_position, last_event_timestamp_micros,
                    last_committed_at, events_replicated_count
                ) VALUES
            """

            values = [
                str(offset.offset_id),
                offset.table_name,
                offset.keyspace,
                offset.partition_id,
                offset.destination.value,
                offset.commitlog_file,
                offset.commitlog_position,
                offset.last_event_timestamp_micros,
                offset.last_committed_at,
                offset.events_replicated_count,
            ]

            self._client.execute(query, [values])

            logger.info("Committed offset to ClickHouse", offset_id=str(offset.offset_id))

        except Exception as e:
            self.increment_errors()
            raise SinkError(f"Failed to commit offset to ClickHouse: {e}") from e

    async def health_check(self) -> bool:
        """
        Check ClickHouse health

        Returns:
            True if healthy, False otherwise
        """
        try:
            if not self._client:
                return False

            self._client.execute("SELECT 1")
            return True

        except Exception as e:
            logger.warning("ClickHouse health check failed", error=str(e))
            return False
