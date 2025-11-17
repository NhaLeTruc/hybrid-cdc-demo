"""
Sinks for writing CDC events to destination warehouses
"""

from src.sinks.base import BaseSink, SinkError
from src.sinks.clickhouse import ClickHouseSink
from src.sinks.postgres import PostgresSink
from src.sinks.timescaledb import TimescaleDBSink

__all__ = [
    "BaseSink",
    "SinkError",
    "PostgresSink",
    "ClickHouseSink",
    "TimescaleDBSink",
]
