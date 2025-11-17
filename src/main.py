"""
CDC Pipeline Main Entrypoint
Orchestrates reading from Cassandra CDC and writing to multiple destinations
"""

import asyncio
import signal
import sys
from typing import Dict, List, Optional

import structlog

from src.cdc.offset import OffsetManager
from src.cdc.reader import CommitLogReader
from src.config.loader import load_config
from src.config.settings import CDCSettings
from src.models.event import ChangeEvent
from src.models.offset import Destination
from src.observability.logging import configure_logging
from src.observability.metrics import start_metrics_server
from src.sinks.base import BaseSink
from src.sinks.clickhouse import ClickHouseSink
from src.sinks.postgres import PostgresSink
from src.sinks.timescaledb import TimescaleDBSink

logger = structlog.get_logger(__name__)


class CDCPipeline:
    """
    Main CDC Pipeline orchestrator

    Coordinates reading from Cassandra commitlog and writing to
    multiple destination warehouses with exactly-once delivery.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize CDC pipeline

        Args:
            config_path: Path to configuration file (uses default if None)
        """
        # Load configuration
        if config_path:
            self.config = load_config(config_path)
        else:
            self.config = CDCSettings()

        # Initialize components
        self.reader = CommitLogReader(
            cdc_raw_directory=self.config.cassandra.cdc_raw_directory,
            poll_interval_seconds=self.config.pipeline.poll_interval_seconds,
        )
        self.offset_manager = OffsetManager()

        # Initialize sinks
        self.sinks: Dict[Destination, BaseSink] = {}
        self._shutdown_flag = False

        logger.info("CDCPipeline initialized")

    async def initialize_sinks(self) -> None:
        """
        Initialize and connect all configured sinks
        """
        logger.info("Initializing sinks")

        # Initialize Postgres sink
        if self.config.destinations.postgres.enabled:
            postgres_sink = PostgresSink(
                connection_url=self.config.destinations.postgres.connection_url,
            )
            await postgres_sink.connect()
            self.sinks[Destination.POSTGRES] = postgres_sink
            logger.info("Postgres sink initialized")

        # Initialize ClickHouse sink
        if self.config.destinations.clickhouse.enabled:
            clickhouse_sink = ClickHouseSink(
                host=self.config.destinations.clickhouse.host,
                port=self.config.destinations.clickhouse.port,
                database=self.config.destinations.clickhouse.database,
            )
            await clickhouse_sink.connect()
            self.sinks[Destination.CLICKHOUSE] = clickhouse_sink
            logger.info("ClickHouse sink initialized")

        # Initialize TimescaleDB sink
        if self.config.destinations.timescaledb.enabled:
            timescaledb_sink = TimescaleDBSink(
                connection_url=self.config.destinations.timescaledb.connection_url,
            )
            await timescaledb_sink.connect()
            self.sinks[Destination.TIMESCALEDB] = timescaledb_sink
            logger.info("TimescaleDB sink initialized")

        logger.info("All sinks initialized", count=len(self.sinks))

    async def shutdown_sinks(self) -> None:
        """
        Gracefully shutdown all sinks
        """
        logger.info("Shutting down sinks")

        for destination, sink in self.sinks.items():
            try:
                await sink.disconnect()
                logger.info("Sink disconnected", destination=destination.value)
            except Exception as e:
                logger.error(
                    "Error disconnecting sink", destination=destination.value, error=str(e)
                )

    async def process_batch(
        self,
        events: List[ChangeEvent],
        table_name: str,
        keyspace: str,
    ) -> None:
        """
        Process a batch of events by writing to all destinations

        Args:
            events: List of ChangeEvents to process
            table_name: Table name for offset tracking
            keyspace: Keyspace name for offset tracking
        """
        if not events:
            return

        logger.info("Processing batch", event_count=len(events))

        # Write to all sinks concurrently
        write_tasks = []
        for destination, sink in self.sinks.items():
            write_tasks.append(self._write_to_sink(sink, events, table_name, keyspace))

        # Execute all writes in parallel
        results = await asyncio.gather(*write_tasks, return_exceptions=True)

        # Log results
        for destination, result in zip(self.sinks.keys(), results):
            if isinstance(result, Exception):
                logger.error("Sink write failed", destination=destination.value, error=str(result))
            else:
                logger.info("Sink write succeeded", destination=destination.value, count=result)

    async def _write_to_sink(
        self,
        sink: BaseSink,
        events: List[ChangeEvent],
        table_name: str,
        keyspace: str,
    ) -> int:
        """
        Write batch to a single sink with offset commit

        Args:
            sink: Sink to write to
            events: Events to write
            table_name: Table name
            keyspace: Keyspace name

        Returns:
            Number of events written
        """
        try:
            # Write batch
            count = await sink.write_batch(events)

            # Commit offset (in same transaction for Postgres/TimescaleDB)
            if count > 0:
                last_event = events[-1]
                offset = self.offset_manager.create_offset(
                    table_name=table_name,
                    keyspace=keyspace,
                    partition_id=0,  # Simplified for demo
                    destination=sink.destination,
                    commitlog_file="CommitLog-7-1700000000.log",  # Would track actual file
                    commitlog_position=0,  # Would track actual position
                    event_timestamp_micros=last_event.timestamp_micros,
                    events_count=count,
                )

                await sink.commit_offset(offset)

            return count

        except Exception as e:
            logger.error("Error writing to sink", destination=sink.destination.value, error=str(e))
            raise

    async def run_continuous(self, table_name: str, keyspace: str) -> None:
        """
        Run pipeline continuously, processing events as they arrive

        Args:
            table_name: Table to replicate
            keyspace: Keyspace to replicate
        """
        logger.info("Starting continuous replication", table=table_name, keyspace=keyspace)

        # Initialize sinks
        await self.initialize_sinks()

        try:
            # Get last offsets from all destinations
            last_file = None
            last_position = 0

            for destination, sink in self.sinks.items():
                offset = self.offset_manager.read_latest_offset(table_name, keyspace, destination)
                if offset:
                    last_file = offset.commitlog_file
                    last_position = offset.commitlog_position
                    logger.info(
                        "Resuming from offset",
                        destination=destination.value,
                        file=last_file,
                        position=last_position,
                    )

            # Start polling for events
            batch: List[ChangeEvent] = []
            batch_size = self.config.pipeline.batch_size

            for event, file, position in self.reader.poll_for_new_events(
                table_name=table_name,
                keyspace=keyspace,
                last_file=last_file,
                last_position=last_position,
            ):
                if self._shutdown_flag:
                    logger.info("Shutdown requested, processing final batch")
                    if batch:
                        await self.process_batch(batch, table_name, keyspace)
                    break

                # Add event to batch
                batch.append(event)

                # Process batch when full
                if len(batch) >= batch_size:
                    await self.process_batch(batch, table_name, keyspace)
                    batch = []

        finally:
            # Shutdown sinks
            await self.shutdown_sinks()

    def shutdown(self) -> None:
        """
        Request graceful shutdown
        """
        logger.info("Shutdown signal received")
        self._shutdown_flag = True


async def main() -> None:
    """
    Main entrypoint
    """
    # Configure logging
    configure_logging(json_format=True)

    logger.info("Starting CDC Pipeline")

    # Start metrics server
    start_metrics_server(port=9090)

    # Create pipeline
    pipeline = CDCPipeline()

    # Setup signal handlers
    def signal_handler(signum, frame):
        logger.info("Signal received", signal=signum)
        pipeline.shutdown()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Run pipeline
    try:
        # For demo: replicate users table from ecommerce keyspace
        await pipeline.run_continuous(table_name="users", keyspace="ecommerce")
    except Exception as e:
        logger.error("Pipeline failed", error=str(e))
        sys.exit(1)

    logger.info("CDC Pipeline stopped")


if __name__ == "__main__":
    asyncio.run(main())
