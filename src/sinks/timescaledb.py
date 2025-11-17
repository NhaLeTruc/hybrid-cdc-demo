"""
TimescaleDB Sink
Writes CDC events to TimescaleDB warehouse with hypertable support
"""

from typing import List

import structlog

from src.models.event import ChangeEvent
from src.models.offset import Destination
from src.sinks.base import SinkError
from src.sinks.postgres import PostgresSink

logger = structlog.get_logger(__name__)


class TimescaleDBSink(PostgresSink):
    """
    TimescaleDB sink inheriting from PostgresSink

    Adds hypertable-specific features on top of Postgres functionality.
    """

    def __init__(
        self,
        connection_url: str,
        schema: str = "public",
        enable_compression: bool = True,
    ):
        """
        Initialize TimescaleDB sink

        Args:
            connection_url: TimescaleDB connection URL
            schema: Database schema to use
            enable_compression: Enable compression for hypertables
        """
        # Initialize as Postgres sink but with TIMESCALEDB destination
        super().__init__(connection_url, schema)
        self.destination = Destination.TIMESCALEDB  # Override destination
        self.enable_compression = enable_compression

        logger.info("TimescaleDBSink initialized", enable_compression=enable_compression)

    async def connect(self) -> None:
        """
        Establish async connection to TimescaleDB

        Raises:
            SinkError: If connection fails
        """
        # Use parent Postgres connection logic
        await super().connect()

        # Verify TimescaleDB extension is available
        try:
            async with self._conn.cursor() as cur:
                await cur.execute("SELECT extname FROM pg_extension WHERE extname = 'timescaledb'")
                result = await cur.fetchone()

                if not result:
                    logger.warning("TimescaleDB extension not found")
                else:
                    logger.info("TimescaleDB extension verified")

        except Exception as e:
            logger.warning("Could not verify TimescaleDB extension", error=str(e))

    async def write_batch(self, events: List[ChangeEvent]) -> int:
        """
        Write batch of events to TimescaleDB

        Uses parent PostgresSink write logic. TimescaleDB is fully Postgres-compatible.

        Args:
            events: List of ChangeEvents to write

        Returns:
            Number of events successfully written

        Raises:
            SinkError: If write fails
        """
        # Use parent Postgres write logic
        # Hypertables work transparently with standard INSERT statements
        return await super().write_batch(events)

    async def ensure_hypertable(self, table_name: str, time_column: str = "created_at") -> None:
        """
        Ensure table is converted to hypertable

        Args:
            table_name: Name of table to convert
            time_column: Column to use for time partitioning

        Raises:
            SinkError: If hypertable creation fails
        """
        if not self._conn:
            raise SinkError("Not connected to TimescaleDB")

        try:
            async with self._conn.cursor() as cur:
                # Check if already a hypertable
                query = """
                    SELECT * FROM timescaledb_information.hypertables
                    WHERE hypertable_schema = %s AND hypertable_name = %s
                """
                await cur.execute(query, (self.schema, table_name))
                result = await cur.fetchone()

                if not result:
                    # Create hypertable
                    full_table_name = f"{self.schema}.{table_name}"
                    create_query = f"SELECT create_hypertable('{full_table_name}', '{time_column}', if_not_exists => TRUE)"
                    await cur.execute(create_query)
                    await self._conn.commit()

                    logger.info("Created hypertable", table=table_name, time_column=time_column)

                    # Enable compression if configured
                    if self.enable_compression:
                        compress_query = f"""
                            ALTER TABLE {full_table_name}
                            SET (timescaledb.compress,
                                 timescaledb.compress_segmentby = '{time_column}')
                        """
                        await cur.execute(compress_query)
                        await self._conn.commit()

                        logger.info("Enabled compression for hypertable", table=table_name)

                else:
                    logger.debug("Table is already a hypertable", table=table_name)

        except Exception as e:
            self.increment_errors()
            raise SinkError(f"Failed to ensure hypertable for {table_name}: {e}") from e

    async def health_check(self) -> bool:
        """
        Check TimescaleDB health

        Returns:
            True if healthy, False otherwise
        """
        # Use parent Postgres health check
        # Also verify TimescaleDB-specific features
        if not await super().health_check():
            return False

        try:
            async with self._conn.cursor() as cur:
                # Check TimescaleDB version
                await cur.execute(
                    "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'"
                )
                version = await cur.fetchone()
                if version:
                    logger.debug("TimescaleDB version", version=version[0])
                    return True
                return False

        except Exception as e:
            logger.warning("TimescaleDB health check failed", error=str(e))
            return False
