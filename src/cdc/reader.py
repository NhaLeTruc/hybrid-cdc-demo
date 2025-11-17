"""
Cassandra CDC Commitlog Reader
Reads commitlog files from Cassandra cdc_raw directory
"""

import time
from pathlib import Path
from typing import Iterator, List, Optional

import structlog

from src.cdc.parser import ParseError, parse_commitlog_entry
from src.models.event import ChangeEvent

logger = structlog.get_logger(__name__)


class CommitLogReader:
    """
    Reads Cassandra CDC commitlog files and yields ChangeEvents

    For tech demo: Simplified commitlog reading.
    Production would integrate with Cassandra's commitlog reader library.
    """

    def __init__(
        self,
        cdc_raw_directory: str = "/var/lib/cassandra/cdc_raw",
        poll_interval_seconds: float = 1.0,
    ):
        """
        Initialize CommitLog reader

        Args:
            cdc_raw_directory: Path to Cassandra cdc_raw directory
            poll_interval_seconds: How often to poll for new commitlog files
        """
        self.cdc_raw_directory = Path(cdc_raw_directory)
        self.poll_interval_seconds = poll_interval_seconds
        self._current_file: Optional[Path] = None
        self._current_position: int = 0
        self._processed_files: set[str] = set()

        logger.info("CommitLogReader initialized", cdc_directory=str(self.cdc_raw_directory))

    def read_events(
        self,
        table_name: str,
        keyspace: str,
        start_file: Optional[str] = None,
        start_position: int = 0,
    ) -> Iterator[tuple[ChangeEvent, str, int]]:
        """
        Read CDC events from commitlog files

        Args:
            table_name: Filter events for this table
            keyspace: Filter events for this keyspace
            start_file: Resume from this commitlog file (None to start from oldest)
            start_position: Resume from this byte position in start_file

        Yields:
            Tuples of (event, commitlog_file, position)
        """
        logger.info(
            "Starting to read events",
            table=table_name,
            keyspace=keyspace,
            start_file=start_file,
            start_position=start_position,
        )

        # Get list of commitlog files
        commitlog_files = self._get_commitlog_files()

        if not commitlog_files:
            logger.warning("No commitlog files found in cdc_raw directory")
            return

        # Find starting point
        if start_file:
            # Resume from specific file
            try:
                start_index = [f.name for f in commitlog_files].index(start_file)
                commitlog_files = commitlog_files[start_index:]
            except ValueError:
                logger.warning("Start file not found, beginning from oldest", start_file=start_file)

        # Read each commitlog file
        for commitlog_file in commitlog_files:
            if commitlog_file.name in self._processed_files:
                logger.debug("Skipping already processed file", file=commitlog_file.name)
                continue

            logger.info("Processing commitlog file", file=commitlog_file.name)

            # Determine starting position for this file
            position = start_position if commitlog_file.name == start_file else 0

            # Read events from file
            try:
                yield from self._read_file_events(commitlog_file, table_name, keyspace, position)

                # Mark file as processed
                self._processed_files.add(commitlog_file.name)

            except Exception as e:
                logger.error("Error reading commitlog file", file=commitlog_file.name, error=str(e))
                # Continue with next file instead of crashing
                continue

    def _get_commitlog_files(self) -> List[Path]:
        """
        Get sorted list of commitlog files from cdc_raw directory

        Returns:
            List of Path objects sorted by filename (oldest first)
        """
        if not self.cdc_raw_directory.exists():
            logger.warning("CDC directory does not exist", path=str(self.cdc_raw_directory))
            return []

        # Find all .log files matching CommitLog pattern
        commitlog_files = sorted(
            [f for f in self.cdc_raw_directory.glob("CommitLog-*.log")],
            key=lambda f: f.name,
        )

        logger.debug("Found commitlog files", count=len(commitlog_files))
        return commitlog_files

    def _read_file_events(
        self,
        commitlog_file: Path,
        table_name: str,
        keyspace: str,
        start_position: int = 0,
    ) -> Iterator[tuple[ChangeEvent, str, int]]:
        """
        Read events from a single commitlog file

        Args:
            commitlog_file: Path to commitlog file
            table_name: Filter for this table
            keyspace: Filter for this keyspace
            start_position: Start reading from this byte position

        Yields:
            Tuples of (event, commitlog_file_name, position)
        """
        try:
            with open(commitlog_file, "rb") as f:
                # Seek to starting position
                if start_position > 0:
                    f.seek(start_position)
                    logger.debug("Resuming from position", position=start_position)

                # Read entries until end of file
                while True:
                    position = f.tell()

                    # Read entry size (4 bytes)
                    size_bytes = f.read(4)
                    if not size_bytes or len(size_bytes) < 4:
                        # End of file
                        break

                    entry_size = int.from_bytes(size_bytes, byteorder="big")
                    if entry_size == 0 or entry_size > 100_000_000:  # Sanity check
                        logger.warning(
                            "Invalid entry size, skipping", size=entry_size, position=position
                        )
                        break

                    # Read entry data
                    entry_data = f.read(entry_size)
                    if len(entry_data) < entry_size:
                        # Incomplete entry (file might still be written)
                        logger.debug("Incomplete entry, waiting for more data")
                        break

                    # Parse entry
                    try:
                        event = parse_commitlog_entry(entry_data)

                        # Filter by table and keyspace
                        if event.table_name == table_name and event.keyspace == keyspace:
                            yield (event, commitlog_file.name, position)

                    except ParseError as e:
                        logger.warning(
                            "Failed to parse commitlog entry",
                            position=position,
                            error=str(e),
                        )
                        # Continue to next entry
                        continue

        except IOError as e:
            logger.error("IO error reading commitlog file", file=str(commitlog_file), error=str(e))
            raise

    def poll_for_new_events(
        self,
        table_name: str,
        keyspace: str,
        last_file: Optional[str] = None,
        last_position: int = 0,
    ) -> Iterator[tuple[ChangeEvent, str, int]]:
        """
        Continuously poll for new CDC events

        Args:
            table_name: Filter events for this table
            keyspace: Filter events for this keyspace
            last_file: Last processed commitlog file
            last_position: Last processed position

        Yields:
            Tuples of (event, commitlog_file, position)
        """
        logger.info("Starting continuous polling for new events")

        while True:
            # Read any available events
            event_count = 0
            for event, file, position in self.read_events(
                table_name=table_name,
                keyspace=keyspace,
                start_file=last_file,
                start_position=last_position,
            ):
                yield (event, file, position)
                last_file = file
                last_position = position
                event_count += 1

            if event_count > 0:
                logger.debug("Processed events in poll cycle", count=event_count)

            # Wait before next poll
            time.sleep(self.poll_interval_seconds)
