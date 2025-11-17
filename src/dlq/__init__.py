"""
Dead Letter Queue (DLQ) module
Handles events that fail after max retries
"""

from src.dlq.writer import DLQWriter

__all__ = ["DLQWriter"]
