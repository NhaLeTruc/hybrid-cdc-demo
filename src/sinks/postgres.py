"""
PostgreSQL Sink
Writes CDC events to Postgres warehouse using async psycopg
"""

from typing import List, Optional
import structlog
from psycopg import AsyncConnection
from psycopg.rows import dict_row

from src.sinks.base import BaseSink, SinkError
from src.models.event import ChangeEvent, EventType
from src.models.offset import ReplicationOffset, Destination

logger = structlog.get_logger(__name__)


class PostgresSink(BaseSink):
    """
    Postgres sink with exactly-once delivery using INSERT ... ON CONFLICT
    """

    def __init__(
        self,
        connection_url: str,
        schema: str = "public",
    ):
        """
        Initialize Postgres sink

        Args:
            connection_url: Postgres connection URL
            schema: Database schema to use
        """
        super().__init__(Destination.POSTGRES)
        self.connection_url = connection_url
        self.schema = schema
        self._conn: Optional[AsyncConnection] = None

    async def connect(self) -> None:
        """
        Establish async connection to Postgres

        Raises:
            SinkError: If connection fails
        """
        try:
            self._conn = await AsyncConnection.connect(
                self.connection_url,
                row_factory=dict_row,
                autocommit=False,  # Use transactions for exactly-once
            )
            self.is_connected = True
            logger.info("Connected to Postgres", schema=self.schema)

        except Exception as e:
            self.increment_errors()
            raise SinkError(f"Failed to connect to Postgres: {e}") from e

    async def disconnect(self) -> None:
        """Close Postgres connection"""
        if self._conn:
            await self._conn.close()
            self.is_connected = False
            logger.info("Disconnected from Postgres")

    async def write_batch(self, events: List[ChangeEvent]) -> int:
        """
        Write batch of events to Postgres using INSERT ... ON CONFLICT

        Args:
            events: List of ChangeEvents to write

        Returns:
            Number of events successfully written

        Raises:
            SinkError: If write fails
        """
        if not self._conn:
            raise SinkError("Not connected to Postgres")

        if not events:
            return 0

        try:
            async with self._conn.cursor() as cur:
                written_count = 0

                for event in events:
                    # Build INSERT query with ON CONFLICT for idempotency
                    if event.event_type == EventType.DELETE:
                        # Handle DELETE
                        table = f"{self.schema}.{event.table_name}"
                        partition_key_cols = list(event.partition_key.keys())
                        where_clause = " AND ".join([f"{col} = %s" for col in partition_key_cols])
                        query = f"DELETE FROM {table} WHERE {where_clause}"
                        params = list(event.partition_key.values())

                        await cur.execute(query, params)

                    else:
                        # Handle INSERT/UPDATE
                        table = f"{self.schema}.{event.table_name}"

                        # Combine partition key, clustering key, and columns
                        all_columns = {
                            **event.partition_key,
                            **event.clustering_key,
                            **event.columns,
                        }

                        # Build column lists
                        columns = list(all_columns.keys())
                        placeholders = ["%s"] * len(columns)
                        values = list(all_columns.values())

                        # Primary key for ON CONFLICT (partition + clustering keys)
                        pk_cols = list(event.partition_key.keys()) + list(event.clustering_key.keys())

                        # Build INSERT ... ON CONFLICT query
                        query = f"""
                            INSERT INTO {table} ({', '.join(columns)})
                            VALUES ({', '.join(placeholders)})
                            ON CONFLICT ({', '.join(pk_cols)})
                            DO UPDATE SET {', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col not in pk_cols])}
                        """

                        await cur.execute(query, values)

                    written_count += 1

                # Commit transaction (will be committed with offset)
                # await self._conn.commit()

                self.increment_events_written(written_count)
                logger.info("Wrote batch to Postgres", count=written_count)
                return written_count

        except Exception as e:
            self.increment_errors()
            await self._conn.rollback()
            raise SinkError(f"Failed to write batch to Postgres: {e}") from e

    async def commit_offset(self, offset: ReplicationOffset) -> None:
        """
        Commit offset to Postgres within same transaction as data

        Args:
            offset: Offset to commit

        Raises:
            SinkError: If commit fails
        """
        if not self._conn:
            raise SinkError("Not connected to Postgres")

        try:
            async with self._conn.cursor() as cur:
                # Insert or update offset in offset table
                query = """
                    INSERT INTO cdc_offsets (
                        offset_id, table_name, keyspace, partition_id, destination,
                        commitlog_file, commitlog_position, last_event_timestamp_micros,
                        last_committed_at, events_replicated_count
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (table_name, keyspace, partition_id, destination)
                    DO UPDATE SET
                        offset_id = EXCLUDED.offset_id,
                        commitlog_file = EXCLUDED.commitlog_file,
                        commitlog_position = EXCLUDED.commitlog_position,
                        last_event_timestamp_micros = EXCLUDED.last_event_timestamp_micros,
                        last_committed_at = EXCLUDED.last_committed_at,
                        events_replicated_count = cdc_offsets.events_replicated_count + EXCLUDED.events_replicated_count
                """

                await cur.execute(
                    query,
                    (
                        offset.offset_id,
                        offset.table_name,
                        offset.keyspace,
                        offset.partition_id,
                        offset.destination.value,
                        offset.commitlog_file,
                        offset.commitlog_position,
                        offset.last_event_timestamp_micros,
                        offset.last_committed_at,
                        offset.events_replicated_count,
                    ),
                )

            # Commit transaction (both data and offset)
            await self._conn.commit()

            logger.info("Committed offset to Postgres", offset_id=str(offset.offset_id))

        except Exception as e:
            self.increment_errors()
            await self._conn.rollback()
            raise SinkError(f"Failed to commit offset to Postgres: {e}") from e

    async def health_check(self) -> bool:
        """
        Check Postgres health

        Returns:
            True if healthy, False otherwise
        """
        try:
            if not self._conn:
                return False

            async with self._conn.cursor() as cur:
                await cur.execute("SELECT 1")
                return True

        except Exception as e:
            logger.warning("Postgres health check failed", error=str(e))
            return False
