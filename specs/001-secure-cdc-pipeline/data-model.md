# Data Model

**Feature**: Secure Multi-Destination CDC Pipeline
**Date**: 2025-11-17
**Source**: Extracted from [spec.md](spec.md) Key Entities section

## Overview

This document defines the core data entities used throughout the CDC pipeline, from change event capture through transformation to warehouse replication. All entities are implemented as Python dataclasses with type hints for validation.

## Entity Definitions

### 1. ChangeEvent

**Purpose**: Represents a single data modification (INSERT, UPDATE, DELETE) captured from Cassandra commitlog.

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| event_id | UUID | Yes | Unique identifier for this event (for deduplication and correlation) |
| event_type | Enum[INSERT, UPDATE, DELETE] | Yes | Type of change operation |
| table_name | str | Yes | Cassandra table name (e.g., "users", "orders") |
| keyspace | str | Yes | Cassandra keyspace (database) |
| partition_key | dict[str, Any] | Yes | Partition key columns and values {column: value} |
| clustering_key | dict[str, Any] | No | Clustering key columns and values (None for single-row partition) |
| columns | dict[str, Any] | Yes (except DELETE) | Changed column values {column: value} |
| timestamp_micros | int | Yes | Cassandra writetime (microseconds since epoch) |
| ttl_seconds | int | No | Time-to-live for inserted row (None if no TTL) |
| captured_at | datetime | Yes | When pipeline read this event from commitlog |

**Relationships**:
- References `SchemaVersion` for table schema validation
- Transformed via `MaskedField` rules before sinking
- Tracked by `ReplicationOffset` for delivery guarantees

**Validations**:
- `event_type` must be one of: INSERT, UPDATE, DELETE
- `partition_key` must be non-empty dict
- `columns` required for INSERT/UPDATE, empty for DELETE
- `timestamp_micros` must be positive integer
- `captured_at` must be <= current time

**State Transitions**:
```
Captured → Validated → Masked → Replicated → Committed
                ↓
            Failed → DeadLetterEvent
```

**Example**:
```python
ChangeEvent(
    event_id=UUID("a1b2c3..."),
    event_type=EventType.UPDATE,
    table_name="users",
    keyspace="production",
    partition_key={"user_id": "user_12345"},
    clustering_key={},
    columns={"email": "user@example.com", "age": 30},
    timestamp_micros=1700000000000000,
    ttl_seconds=None,
    captured_at=datetime(2025, 11, 17, 10, 30, 0)
)
```

---

### 2. ReplicationOffset

**Purpose**: Tracks pipeline progress per Cassandra partition and per destination warehouse to enable exactly-once delivery and crash recovery.

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| offset_id | UUID | Yes | Unique identifier for this offset record |
| table_name | str | Yes | Cassandra table being replicated |
| keyspace | str | Yes | Cassandra keyspace |
| partition_id | int | Yes | Cassandra partition token range identifier |
| destination | Enum[POSTGRES, CLICKHOUSE, TIMESCALEDB] | Yes | Which warehouse this offset applies to |
| commitlog_file | str | Yes | Cassandra commitlog file path (e.g., "CommitLog-7-123456.log") |
| commitlog_position | int | Yes | Byte offset within commitlog file |
| last_event_timestamp_micros | int | Yes | Timestamp of last successfully replicated event |
| last_committed_at | datetime | Yes | When this offset was committed (for lag calculation) |
| events_replicated_count | int | Yes | Total events replicated for this partition (counter) |

**Relationships**:
- One offset per (table, partition, destination) tuple
- Updated atomically with `ChangeEvent` sink writes
- Used by CDC reader to resume from last committed position

**Validations**:
- `partition_id` must be valid Cassandra token range (-2^63 to 2^63-1)
- `commitlog_position` must be non-negative
- `last_event_timestamp_micros` must be monotonically increasing (cannot go backwards)
- `last_committed_at` must be <= current time

**Persistence**:
- Stored in Postgres `_cdc_offsets` table (primary offset store)
- Replicated to ClickHouse/TimescaleDB for redundancy (eventual consistency acceptable)

**Example**:
```python
ReplicationOffset(
    offset_id=UUID("d4e5f6..."),
    table_name="users",
    keyspace="production",
    partition_id=42,
    destination=Destination.POSTGRES,
    commitlog_file="CommitLog-7-1700000000.log",
    commitlog_position=1048576,  # 1MB into file
    last_event_timestamp_micros=1700000000000000,
    last_committed_at=datetime(2025, 11, 17, 10, 30, 5),
    events_replicated_count=15678
)
```

---

### 3. MaskedField

**Purpose**: Represents a field classified as PII/PHI with its masking strategy and transformation result.

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| field_name | str | Yes | Original column name (e.g., "email", "ssn") |
| classification | Enum[PII, PHI, SENSITIVE] | Yes | Data sensitivity classification |
| masking_strategy | Enum[HASH, HMAC, TOKENIZE, PASSTHROUGH] | Yes | Transformation method |
| original_value | Any | No | Original value (only logged, never stored in warehouse) |
| masked_value | str | Yes | Transformed value (hashed/tokenized) |
| salt | str | No | Salt used for hashing (if applicable) |
| key_id | str | No | Key identifier for HMAC/tokenization (if applicable) |
| masked_at | datetime | Yes | When masking occurred (for audit trail) |

**Relationships**:
- Applied to `ChangeEvent.columns` during transformation phase
- Configuration loaded from `config/masking-rules.yaml`
- Audit logged via observability layer

**Validations**:
- `field_name` must match column in ChangeEvent
- `masking_strategy` = HASH → `masked_value` is SHA-256 hex digest (64 chars)
- `masking_strategy` = HMAC → `key_id` must be provided
- `masking_strategy` = PASSTHROUGH → `masked_value` = `original_value` (no transformation)
- `masked_at` must be between event capture and sink write

**Masking Rules**:
| Classification | Default Strategy | Use Case |
|---------------|-----------------|----------|
| PII | HASH (SHA-256) | Irreversible for email, phone, SSN |
| PHI | HMAC (deterministic token) | Medical records requiring analytics |
| SENSITIVE | Configurable | Domain-specific (credit card, etc.) |

**Example**:
```python
MaskedField(
    field_name="email",
    classification=Classification.PII,
    masking_strategy=MaskingStrategy.HASH,
    original_value="user@example.com",
    masked_value="5d41402abc4b2a76b9719d911017c592",  # SHA-256 hash
    salt="random_salt_123",
    key_id=None,
    masked_at=datetime(2025, 11, 17, 10, 30, 1)
)
```

---

### 4. DestinationSink

**Purpose**: Represents connection and health state for one of three data warehouse destinations.

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| sink_id | UUID | Yes | Unique identifier for this sink instance |
| destination | Enum[POSTGRES, CLICKHOUSE, TIMESCALEDB] | Yes | Warehouse type |
| connection_string | str | Yes | Database connection URL (redacted in logs) |
| is_connected | bool | Yes | Current connection health status |
| last_health_check | datetime | Yes | When health was last verified |
| backlog_depth | int | Yes | Number of uncommitted events buffered |
| throughput_eps | float | Yes | Current events per second (moving average) |
| error_count_last_minute | int | Yes | Errors in rolling 60-second window |
| total_events_written | int | Yes | Lifetime event counter |
| connection_pool_size | int | Yes | Max concurrent connections to warehouse |
| retry_policy | RetryPolicy | Yes | Retry configuration for this sink |

**Relationships**:
- One sink instance per destination warehouse
- Writes `ChangeEvent` batches to destination
- Commits `ReplicationOffset` atomically with writes

**Validations**:
- `connection_string` must be valid database URL (validated by pydantic)
- `backlog_depth` must be non-negative
- `throughput_eps` must be non-negative
- `connection_pool_size` must be > 0
- `last_health_check` should be recent (warn if > 60s old)

**State Diagram**:
```
DISCONNECTED → CONNECTING → CONNECTED
       ↑            ↓              ↓
       └─────── FAILED ←───────────┘
                  ↓
              RETRYING
```

**Example**:
```python
DestinationSink(
    sink_id=UUID("g7h8i9..."),
    destination=Destination.POSTGRES,
    connection_string="postgresql://user:***@localhost:5432/warehouse",
    is_connected=True,
    last_health_check=datetime(2025, 11, 17, 10, 30, 10),
    backlog_depth=0,
    throughput_eps=850.5,
    error_count_last_minute=0,
    total_events_written=1234567,
    connection_pool_size=10,
    retry_policy=RetryPolicy(max_attempts=5, backoff_multiplier=2.0)
)
```

---

### 5. DeadLetterEvent

**Purpose**: Failed event that exceeded retry limits, stored for manual inspection and recovery.

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| dlq_id | UUID | Yes | Unique DLQ entry identifier |
| original_event | ChangeEvent | Yes | Full original event that failed |
| destination | Enum[POSTGRES, CLICKHOUSE, TIMESCALEDB] | Yes | Which sink failed |
| error_type | str | Yes | Exception class name (e.g., "ConnectionError") |
| error_message | str | Yes | Human-readable error description |
| stack_trace | str | Yes | Full Python stack trace for debugging |
| retry_count | int | Yes | Number of retry attempts before DLQ |
| first_failure_at | datetime | Yes | When first failure occurred |
| dlq_written_at | datetime | Yes | When written to DLQ |

**Relationships**:
- Contains full `ChangeEvent` for potential replay
- References `DestinationSink` that failed
- No automatic recovery (manual inspection required)

**Validations**:
- `retry_count` must be >= configured `max_attempts`
- `first_failure_at` must be <= `dlq_written_at`
- `error_type` and `error_message` must be non-empty
- `stack_trace` should contain Python traceback format

**Persistence**:
- JSONL file: `data/dlq/failed_events_YYYY-MM-DD.jsonl`
- One JSON object per line for easy grep/parsing
- Optional: Postgres table `_cdc_dead_letter_queue` for queryability

**Recovery Process**:
1. Inspect DLQ entry to identify root cause
2. Fix issue (schema, config, network)
3. Replay event manually via admin CLI tool
4. Mark DLQ entry as resolved

**Example**:
```python
DeadLetterEvent(
    dlq_id=UUID("j1k2l3..."),
    original_event=ChangeEvent(...),
    destination=Destination.CLICKHOUSE,
    error_type="ClickHouseError",
    error_message="Unknown column 'new_field' in table 'users'",
    stack_trace="Traceback (most recent call last):\n  File ...",
    retry_count=5,
    first_failure_at=datetime(2025, 11, 17, 10, 29, 0),
    dlq_written_at=datetime(2025, 11, 17, 10, 30, 15)
)
```

---

### 6. SchemaVersion

**Purpose**: Snapshot of Cassandra table schema at a point in time to detect schema evolution and validate type mappings.

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| schema_id | UUID | Yes | Unique identifier for this schema version |
| table_name | str | Yes | Cassandra table name |
| keyspace | str | Yes | Cassandra keyspace |
| version_number | int | Yes | Monotonically increasing version (1, 2, 3...) |
| columns | dict[str, ColumnDef] | Yes | Column definitions {name: {type, is_pk, is_ck}} |
| partition_keys | list[str] | Yes | Ordered list of partition key columns |
| clustering_keys | list[str] | Yes | Ordered list of clustering key columns |
| detected_at | datetime | Yes | When this schema version was detected |
| previous_version | int | No | Previous schema version number (None for initial) |
| schema_changes | list[SchemaChange] | No | Diff from previous version (ADD/DROP/ALTER column) |

**Relationships**:
- `ChangeEvent` validated against current `SchemaVersion`
- Schema changes trigger validation and potential DLQ routing
- Used by `schema_mapper` to generate warehouse DDL

**Validations**:
- `version_number` must be monotonically increasing
- `partition_keys` must be non-empty
- All columns in `partition_keys` and `clustering_keys` must exist in `columns`
- `schema_changes` only present if `version_number` > 1

**ColumnDef Structure**:
```python
ColumnDef(
    name: str,
    cql_type: str,  # e.g., "TEXT", "INT", "UUID", "MAP<TEXT, INT>"
    is_partition_key: bool,
    is_clustering_key: bool,
    is_static: bool
)
```

**SchemaChange Structure**:
```python
SchemaChange(
    change_type: Enum[ADD_COLUMN, DROP_COLUMN, ALTER_TYPE],
    column_name: str,
    old_type: str | None,
    new_type: str | None
)
```

**Example**:
```python
SchemaVersion(
    schema_id=UUID("m4n5o6..."),
    table_name="users",
    keyspace="production",
    version_number=2,
    columns={
        "user_id": ColumnDef("user_id", "UUID", True, False, False),
        "email": ColumnDef("email", "TEXT", False, False, False),
        "age": ColumnDef("age", "INT", False, False, False),
        "created_at": ColumnDef("created_at", "TIMESTAMP", False, False, False)
    },
    partition_keys=["user_id"],
    clustering_keys=[],
    detected_at=datetime(2025, 11, 17, 10, 0, 0),
    previous_version=1,
    schema_changes=[
        SchemaChange(
            change_type=ChangeType.ADD_COLUMN,
            column_name="created_at",
            old_type=None,
            new_type="TIMESTAMP"
        )
    ]
)
```

---

## Entity Relationships Diagram

```
┌─────────────────┐
│  SchemaVersion  │
│  (Cassandra)    │
└────────┬────────┘
         │ validates
         ↓
┌─────────────────┐     ┌──────────────┐
│  ChangeEvent    │────→│ MaskedField  │
│  (CDC capture)  │     │ (transform)  │
└────────┬────────┘     └──────────────┘
         │
         ├──→ Success ──────────────────────┐
         │                                   ↓
         │                          ┌─────────────────┐
         │                          │ DestinationSink │
         │                          │ (Postgres/      │
         │                          │  ClickHouse/    │
         │                          │  TimescaleDB)   │
         │                          └────────┬────────┘
         │                                   │
         │                                   ↓
         │                          ┌──────────────────┐
         │                          │ ReplicationOffset│
         │                          │ (exactly-once)   │
         │                          └──────────────────┘
         │
         └──→ Failure ──────────────────────┐
                                             ↓
                                    ┌─────────────────┐
                                    │ DeadLetterEvent │
                                    │ (manual review) │
                                    └─────────────────┘
```

## Implementation Notes

### Python Dataclass Example

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID
from typing import Any, Optional

class EventType(str, Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"

@dataclass
class ChangeEvent:
    event_id: UUID
    event_type: EventType
    table_name: str
    keyspace: str
    partition_key: dict[str, Any]
    clustering_key: dict[str, Any]
    columns: dict[str, Any]
    timestamp_micros: int
    ttl_seconds: Optional[int]
    captured_at: datetime

    def __post_init__(self):
        # Validation logic
        assert self.timestamp_micros > 0
        assert len(self.partition_key) > 0
        if self.event_type != EventType.DELETE:
            assert len(self.columns) > 0
```

### Database Schemas

**Postgres Offset Table**:
```sql
CREATE TABLE _cdc_offsets (
    offset_id UUID PRIMARY KEY,
    table_name VARCHAR(255) NOT NULL,
    keyspace VARCHAR(255) NOT NULL,
    partition_id BIGINT NOT NULL,
    destination VARCHAR(50) NOT NULL,
    commitlog_file VARCHAR(500) NOT NULL,
    commitlog_position BIGINT NOT NULL,
    last_event_timestamp_micros BIGINT NOT NULL,
    last_committed_at TIMESTAMPTZ NOT NULL,
    events_replicated_count BIGINT NOT NULL,
    UNIQUE (table_name, keyspace, partition_id, destination)
);
CREATE INDEX idx_offsets_lookup ON _cdc_offsets(table_name, partition_id, destination);
```

**Postgres DLQ Table** (optional):
```sql
CREATE TABLE _cdc_dead_letter_queue (
    dlq_id UUID PRIMARY KEY,
    original_event_json JSONB NOT NULL,
    destination VARCHAR(50) NOT NULL,
    error_type VARCHAR(255) NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT NOT NULL,
    retry_count INT NOT NULL,
    first_failure_at TIMESTAMPTZ NOT NULL,
    dlq_written_at TIMESTAMPTZ NOT NULL,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ
);
CREATE INDEX idx_dlq_unresolved ON _cdc_dead_letter_queue(resolved, dlq_written_at);
```

## Next Steps

- Define contracts (JSON schemas, OpenAPI) in `contracts/` directory
- Document quickstart workflow in `quickstart.md`
- Implement dataclasses in `src/models/` with full validation
- Write contract tests validating entity schemas
