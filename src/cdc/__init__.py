"""
CDC (Change Data Capture) module for reading and parsing Cassandra commitlog
"""

from src.cdc.parser import parse_commitlog_entry, ParseError
from src.cdc.reader import CommitLogReader
from src.cdc.offset import OffsetManager

__all__ = ["parse_commitlog_entry", "ParseError", "CommitLogReader", "OffsetManager"]
