# Missing Features Implementation Plan

**Purpose**: Document all missing CDC pipeline features that cause test failures
**Date**: 2025-11-20
**Status**: Planning Phase

---

## Executive Summary

The test suite reveals **35+ missing features** in the CDC pipeline implementation. These are not bugs but **unimplemented functionality** that the tests expect to exist. This document provides a complete implementation roadmap.

---

## Current Test Status

```
Total Tests:        199
Passing:           ~155 (78%)
Failing:            ~44 (22%)

Breakdown:
✅ Infrastructure:  All tests pass (100%)
✅ Unit/Contract:   Most pass (~90%)
❌ Integration:     Many fail (~50%)
```

---

## Missing Features by Category

### Category 1: Schema Evolution System (24 tests failing)

#### 1.1 Schema Change Detection
**Status**: NOT IMPLEMENTED
**Tests Affected**: 24 (test_add_column.py, test_alter_type.py, test_drop_column.py)

**What's Missing**:
- Cassandra schema change monitoring
- Schema version tracking
- Change type classification (ADD_COLUMN, ALTER_TYPE, DROP_COLUMN)
- Automatic schema synchronization

**Implementation Required**:

```python
# New file: src/cdc/schema_monitor.py

class SchemaMonitor:
    """Monitors Cassandra schema changes and triggers synchronization."""

    def __init__(self, cassandra_session, destinations):
        self.session = cassandra_session
        self.destinations = destinations
        self.schema_cache = {}

    async def detect_changes(self, keyspace: str, table: str) -> List[SchemaChange]:
        """
        Detect schema changes by comparing current schema with cached version.

        Returns:
            List of SchemaChange objects representing detected changes
        """
        current_schema = await self._fetch_current_schema(keyspace, table)
        cached_schema = self.schema_cache.get(f"{keyspace}.{table}")

        if cached_schema is None:
            # First time seeing this table
            self.schema_cache[f"{keyspace}.{table}"] = current_schema
            return []

        changes = self._compare_schemas(cached_schema, current_schema)

        if changes:
            self.schema_cache[f"{keyspace}.{table}"] = current_schema

        return changes

    def _compare_schemas(self, old: TableSchema, new: TableSchema) -> List[SchemaChange]:
        """Compare two schemas and identify changes."""
        changes = []

        # Detect added columns
        for col_name, col_def in new.columns.items():
            if col_name not in old.columns:
                changes.append(SchemaChange(
                    change_type=ChangeType.ADD_COLUMN,
                    table_name=new.table,
                    column_name=col_name,
                    old_type=None,
                    new_type=col_def.type,
                ))

        # Detect removed columns
        for col_name in old.columns:
            if col_name not in new.columns:
                changes.append(SchemaChange(
                    change_type=ChangeType.DROP_COLUMN,
                    table_name=new.table,
                    column_name=col_name,
                    old_type=old.columns[col_name].type,
                    new_type=None,
                ))

        # Detect type changes
        for col_name in old.columns:
            if col_name in new.columns:
                if old.columns[col_name].type != new.columns[col_name].type:
                    changes.append(SchemaChange(
                        change_type=ChangeType.ALTER_TYPE,
                        table_name=new.table,
                        column_name=col_name,
                        old_type=old.columns[col_name].type,
                        new_type=new.columns[col_name].type,
                    ))

        return changes

    async def _fetch_current_schema(self, keyspace: str, table: str) -> TableSchema:
        """Fetch current schema from Cassandra system tables."""
        # Query system_schema.columns
        result = self.session.execute(
            """
            SELECT column_name, type, kind
            FROM system_schema.columns
            WHERE keyspace_name = %s AND table_name = %s
            """,
            (keyspace, table)
        )

        columns = {}
        for row in result:
            columns[row.column_name] = ColumnDefinition(
                name=row.column_name,
                type=row.type,
                is_primary_key=(row.kind == 'partition_key' or row.kind == 'clustering'),
            )

        return TableSchema(
            keyspace=keyspace,
            table=table,
            columns=columns,
        )
```

**Integration with CDC Pipeline**:

```python
# In src/main.py - CDCPipeline class

class CDCPipeline:
    def __init__(self, config):
        self.config = config
        self.schema_monitor = SchemaMonitor(
            cassandra_session=self.cassandra_session,
            destinations=self.destinations,
        )

    async def run(self):
        """Main pipeline loop with schema monitoring."""
        while self.running:
            # Monitor for schema changes every iteration
            for keyspace, table in self.monitored_tables:
                changes = await self.schema_monitor.detect_changes(keyspace, table)

                if changes:
                    await self._handle_schema_changes(changes)

            # Process commitlog events
            events = await self.reader.read_batch()
            await self.process_events(events)

    async def _handle_schema_changes(self, changes: List[SchemaChange]):
        """Apply schema changes to all destinations."""
        for change in changes:
            logger.info("Detected schema change", change=change)

            for dest_name, dest_sink in self.destinations.items():
                try:
                    await dest_sink.apply_schema_change(change)
                    logger.info("Applied schema change",
                               destination=dest_name,
                               change=change)
                except Exception as e:
                    logger.error("Failed to apply schema change",
                                destination=dest_name,
                                change=change,
                                error=str(e))
```

**Destination Sink Changes**:

```python
# Add to src/sinks/postgres.py

class PostgresSink(BaseSink):
    async def apply_schema_change(self, change: SchemaChange):
        """Apply schema change to PostgreSQL."""
        mapper = SchemaMapper()

        if change.change_type == ChangeType.ADD_COLUMN:
            # Map Cassandra type to PostgreSQL
            pg_type = mapper.map_cassandra_to_postgres(change.new_type)

            async with self.conn.cursor() as cur:
                await cur.execute(f"""
                    ALTER TABLE {change.table_name}
                    ADD COLUMN {change.column_name} {pg_type}
                """)
            await self.conn.commit()

        elif change.change_type == ChangeType.DROP_COLUMN:
            async with self.conn.cursor() as cur:
                await cur.execute(f"""
                    ALTER TABLE {change.table_name}
                    DROP COLUMN {change.column_name}
                """)
            await self.conn.commit()

        elif change.change_type == ChangeType.ALTER_TYPE:
            # Check if type change is compatible
            if not self._is_compatible_type_change(change.old_type, change.new_type):
                raise SchemaIncompatibilityError(
                    f"Incompatible type change: {change.old_type} -> {change.new_type}"
                )

            pg_type = mapper.map_cassandra_to_postgres(change.new_type)

            async with self.conn.cursor() as cur:
                await cur.execute(f"""
                    ALTER TABLE {change.table_name}
                    ALTER COLUMN {change.column_name} TYPE {pg_type}
                    USING {change.column_name}::{pg_type}
                """)
            await self.conn.commit()
```

**Files to Create**:
1. `src/cdc/schema_monitor.py` - Schema change detection
2. `src/models/schema_change.py` - SchemaChange model (may already exist)

**Files to Modify**:
1. `src/main.py` - Integrate schema monitoring
2. `src/sinks/postgres.py` - Add apply_schema_change()
3. `src/sinks/clickhouse.py` - Add apply_schema_change()
4. `src/sinks/timescaledb.py` - Add apply_schema_change()

**Estimated Time**: 3-4 hours

---

### Category 2: Dead Letter Queue (DLQ) System (11 tests failing)

#### 2.1 Schema Incompatibility Routing
**Status**: PARTIALLY IMPLEMENTED (DLQ writer exists, routing missing)
**Tests Affected**: 11 (test_schema_incompatibility.py)

**What's Missing**:
- Schema validation before writing to destinations
- Automatic routing of incompatible events to DLQ
- DLQ event enrichment with failure details

**Implementation Required**:

```python
# Modify src/sinks/base.py

from src.dlq.writer import DLQWriter
from src.models.dead_letter_event import DeadLetterEvent, FailureReason

class BaseSink:
    """Base class for all destination sinks with DLQ support."""

    def __init__(self, config, dlq_path: str = "/var/lib/cdc/dlq"):
        self.config = config
        self.dlq_writer = DLQWriter(Path(dlq_path))
        self.schema_mapper = SchemaMapper()

    async def write_batch(self, events: List[ChangeEvent]) -> tuple[int, int]:
        """
        Write batch with schema validation and DLQ routing.

        Returns:
            (success_count, dlq_count)
        """
        success = 0
        dlq = 0

        for event in events:
            try:
                # Validate schema compatibility
                validation_result = self._validate_schema(event)

                if not validation_result.is_compatible:
                    # Route to DLQ
                    await self._route_to_dlq(
                        event=event,
                        reason=FailureReason.SCHEMA_INCOMPATIBLE,
                        error_message=validation_result.error_message,
                        schema_details=validation_result.details,
                    )
                    dlq += 1
                    continue

                # Write to destination
                await self._write_single(event)
                success += 1

            except Exception as e:
                logger.error("Failed to write event", error=str(e))
                await self._route_to_dlq(
                    event=event,
                    reason=FailureReason.PROCESSING_ERROR,
                    error_message=str(e),
                )
                dlq += 1

        return success, dlq

    def _validate_schema(self, event: ChangeEvent) -> ValidationResult:
        """
        Validate event schema compatibility with destination.

        Returns:
            ValidationResult with compatibility status and details
        """
        incompatibilities = []

        for col_name, col_value in event.columns.items():
            # Get Cassandra type
            cassandra_type = self._infer_cassandra_type(col_value)

            # Check if type is supported
            try:
                dest_type = self.schema_mapper.map_type(
                    cassandra_type,
                    destination=self.destination_name
                )
            except KeyError:
                incompatibilities.append({
                    "column": col_name,
                    "cassandra_type": cassandra_type,
                    "reason": "Unsupported type",
                })
                continue

            # Check for specific incompatibilities
            if cassandra_type == "tuple":
                incompatibilities.append({
                    "column": col_name,
                    "cassandra_type": cassandra_type,
                    "reason": "Tuple types not supported",
                })
            elif cassandra_type == "counter":
                incompatibilities.append({
                    "column": col_name,
                    "cassandra_type": cassandra_type,
                    "reason": "Counter types not supported",
                })

        if incompatibilities:
            return ValidationResult(
                is_compatible=False,
                error_message=f"Found {len(incompatibilities)} incompatible columns",
                details=incompatibilities,
            )

        return ValidationResult(is_compatible=True)

    async def _route_to_dlq(
        self,
        event: ChangeEvent,
        reason: FailureReason,
        error_message: str,
        schema_details: List[Dict] = None,
    ):
        """Route failed event to Dead Letter Queue with enrichment."""
        from datetime import datetime, timezone

        dlq_event = DeadLetterEvent(
            original_event=event,
            failure_reason=reason,
            error_message=error_message,
            failed_at=datetime.now(timezone.utc),
            retry_count=0,
            destination=self.destination_name,
            schema_details=schema_details or [],
        )

        await self.dlq_writer.write(dlq_event)

        # Update metrics
        self.metrics.increment(
            "events_dlq_total",
            labels={"reason": reason.value, "destination": self.destination_name}
        )
```

**New Models**:

```python
# Add to src/models/validation.py

@dataclass
class ValidationResult:
    """Result of schema validation."""
    is_compatible: bool
    error_message: str = ""
    details: List[Dict[str, str]] = field(default_factory=list)
```

**Update DeadLetterEvent**:

```python
# Modify src/models/dead_letter_event.py

@dataclass
class DeadLetterEvent:
    """Event that failed processing and was sent to DLQ."""
    original_event: ChangeEvent
    failure_reason: FailureReason
    error_message: str
    failed_at: datetime
    retry_count: int
    destination: str = ""  # Add destination
    schema_details: List[Dict] = field(default_factory=list)  # Add schema details
```

**Files to Modify**:
1. `src/sinks/base.py` - Add validation and DLQ routing
2. `src/models/dead_letter_event.py` - Add schema_details field
3. `src/models/validation.py` - Create ValidationResult (new file)

**Estimated Time**: 2-3 hours

---

### Category 3: Health Check System (4 tests failing)

#### 3.1 Configuration Decoupling
**Status**: IMPLEMENTED BUT COUPLED
**Tests Affected**: 4 (test_health_checks.py)

**What's Missing**:
- Independent database settings loading
- Health checks that don't require ALL databases configured

**Implementation Required**:

```python
# Modify src/observability/health.py

async def check_postgres_health() -> DatabaseHealth:
    """Check PostgreSQL health - loads only Postgres settings."""
    try:
        # Only load Postgres settings (not full CDCSettings)
        from src.config.settings import PostgresSettings

        # This will load from environment variables with CDC_POSTGRES_ prefix
        postgres_settings = PostgresSettings()

        # Connect and check
        conn = await psycopg.AsyncConnection.connect(
            host=postgres_settings.host,
            port=postgres_settings.port,
            user=postgres_settings.username or "postgres",
            password=postgres_settings.password or "",
            dbname=postgres_settings.database,
        )

        start = time.time()
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
        latency_ms = (time.time() - start) * 1000

        await conn.close()

        return DatabaseHealth(
            name="postgres",
            status="healthy",
            latency_ms=latency_ms,
            error=None,
        )
    except Exception as e:
        logger.warning("Postgres health check failed", error=str(e))
        return DatabaseHealth(
            name="postgres",
            status="unhealthy",
            latency_ms=None,
            error=str(e),
        )
```

**Update Settings for Independent Loading**:

```python
# Modify src/config/settings.py

from pydantic_settings import BaseSettings, SettingsConfigDict

class PostgresSettings(BaseSettings):
    """Postgres configuration - can be loaded independently."""

    model_config = SettingsConfigDict(
        env_prefix='CDC_POSTGRES_',  # Load from CDC_POSTGRES_* env vars
        case_sensitive=False,
    )

    host: str = Field(default="localhost")
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(default="warehouse")  # Make optional with default
    username: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)
    # ... rest of fields

# Apply same pattern to all Settings classes
```

**Files to Modify**:
1. `src/observability/health.py` - Decouple all health check functions
2. `src/config/settings.py` - Add env_prefix and defaults to all Settings classes

**Estimated Time**: 1-2 hours

---

### Category 4: Business Logic Gaps (8 tests failing)

#### 4.1 TTL Handling in Event Parser
**Status**: PARTIALLY IMPLEMENTED
**Tests Affected**: 3 (test_event_parsing.py)

**Issue**: TTL is extracted in parser but may not be properly passed through ChangeEvent.create()

**Fix Required**:

```python
# Verify src/models/event.py has proper create method

class ChangeEvent:
    @classmethod
    def create(
        cls,
        event_type: EventType,
        table_name: str,
        keyspace: str,
        partition_key: Dict[str, Any],
        clustering_key: Dict[str, Any],
        columns: Dict[str, Any],
        timestamp_micros: int,
        ttl_seconds: Optional[int] = None,  # Ensure this parameter exists
    ) -> "ChangeEvent":
        """Create ChangeEvent with proper validation."""
        return cls(
            event_id=uuid4(),
            event_type=event_type,
            table_name=table_name,
            keyspace=keyspace,
            partition_key=partition_key,
            clustering_key=clustering_key,
            columns=columns,
            timestamp_micros=timestamp_micros,
            captured_at=datetime.now(timezone.utc),
            ttl_seconds=ttl_seconds,  # Pass through TTL
        )
```

**Estimated Time**: 30 minutes

---

#### 4.2 Masking Field Classification
**Status**: CODE UPDATED, CONFIG MISSING
**Tests Affected**: 2 (test_masking.py)

**Issue**: Pattern matching code is correct but defaults aren't being applied

**Fix Required**:

```python
# Modify src/transform/masking.py - ensure defaults work

class MaskingRules:
    def __init__(self):
        # Set defaults immediately, don't wait for load_rules()
        self.pii_fields = [
            "email", "phone", "ssn", "social_security",
            "credit_card", "address", "ip_address", "ip_addr"
        ]
        self.phi_fields = [
            "medical_record", "patient_id", "diagnosis",
            "prescription", "medication", "blood_type"
        ]
        self._loaded = True  # Mark as loaded so classify_field works

    def load_rules(self, config_path: Optional[str] = None) -> None:
        """Load masking rules from YAML - override defaults if file exists."""
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "masking-rules.yaml"

        # Only try to load if file exists
        if not Path(config_path).exists():
            logger.info("Masking config not found, using defaults",
                       pii_count=len(self.pii_fields),
                       phi_count=len(self.phi_fields))
            return

        try:
            with open(config_path) as f:
                rules = yaml.safe_load(f)

            # Override defaults with config
            self.pii_fields = rules.get("pii_fields", self.pii_fields)
            self.phi_fields = rules.get("phi_fields", self.phi_fields)

            logger.info("Masking rules loaded from config",
                       pii_count=len(self.pii_fields),
                       phi_count=len(self.phi_fields))
        except Exception as e:
            logger.error("Failed to load masking config, using defaults", error=str(e))
```

**Estimated Time**: 15 minutes

---

#### 4.3 Offset UPSERT Logic
**Status**: NOT IMPLEMENTED
**Tests Affected**: 1 (test_offset_management.py)

**Fix Required**:

```python
# Modify src/cdc/offset.py

async def write_offset(
    self,
    destination: str,
    partition_id: int,
    commitlog_file: str,
    commitlog_position: int,
    events_processed: int,
) -> None:
    """Write or update offset using UPSERT."""
    from datetime import datetime, timezone

    if destination == "postgres" or destination == "timescaledb":
        conn = self.postgres_conn if destination == "postgres" else self.timescaledb_conn

        async with conn.cursor() as cur:
            # PostgreSQL UPSERT using ON CONFLICT
            await cur.execute(
                """
                INSERT INTO cdc_offsets (
                    destination, partition_id, commitlog_file,
                    commitlog_position, events_processed, last_committed_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (destination, partition_id)
                DO UPDATE SET
                    commitlog_file = EXCLUDED.commitlog_file,
                    commitlog_position = EXCLUDED.commitlog_position,
                    events_processed = cdc_offsets.events_processed + EXCLUDED.events_processed,
                    last_committed_at = EXCLUDED.last_committed_at
                """,
                (destination, partition_id, commitlog_file,
                 commitlog_position, events_processed, datetime.now(timezone.utc))
            )
        await conn.commit()

    elif destination == "clickhouse":
        # ClickHouse uses ReplacingMergeTree for deduplication
        self.clickhouse_client.execute(
            """
            INSERT INTO cdc_offsets
            (destination, partition_id, commitlog_file, commitlog_position,
             events_processed, last_committed_at)
            VALUES
            """,
            [{
                "destination": destination,
                "partition_id": partition_id,
                "commitlog_file": commitlog_file,
                "commitlog_position": commitlog_position,
                "events_processed": events_processed,
                "last_committed_at": datetime.now(timezone.utc),
            }]
        )
```

**Estimated Time**: 45 minutes

---

#### 4.4 TimescaleDB Schema Mapping
**Status**: ALREADY IMPLEMENTED
**Tests Affected**: 1 (test_schema_mapper.py)

**Issue**: Code at line 81 already does `self.timescaledb_mappings = self.postgres_mappings.copy()`

**Verification**: Test should already pass, may be test-specific issue

**Estimated Time**: 10 minutes to verify

---

### Category 5: Integration Test Infrastructure (13+ tests)

#### 5.1 Cassandra Keyspace Creation
**Status**: MISSING IN TESTS
**Tests Affected**: Multiple integration tests

**Issue**: Tests expect `ecommerce` keyspace to exist but it's not created in test fixtures

**Fix Required**:

```python
# Modify tests/conftest.py - cassandra_session fixture

@pytest.fixture(scope="session")
def cassandra_session(cassandra_container: CassandraContainer):
    """Create Cassandra session with ecommerce keyspace."""
    cluster = Cluster(
        [cassandra_container.get_container_host_ip()],
        port=cassandra_container.get_exposed_port(9042),
    )
    session = cluster.connect()

    # Create ecommerce keyspace for integration tests
    session.execute("""
        CREATE KEYSPACE IF NOT EXISTS ecommerce
        WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}
    """)

    # Also create test_keyspace for unit tests
    session.execute("""
        CREATE KEYSPACE IF NOT EXISTS test_keyspace
        WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}
    """)

    session.set_keyspace("ecommerce")  # Default to ecommerce for integration tests

    yield session

    session.shutdown()
    cluster.shutdown()
```

**Estimated Time**: 15 minutes

---

## Implementation Priority

### Phase 1: Quick Wins (2 hours)
1. ✅ Fix masking defaults (15 min)
2. ✅ Verify TTL handling (30 min)
3. ✅ Implement offset UPSERT (45 min)
4. ✅ Add ecommerce keyspace (15 min)
5. ✅ Verify TimescaleDB mapping (15 min)

**Expected Result**: +5-8 tests passing

---

### Phase 2: Health Checks (1-2 hours)
1. ✅ Decouple Postgres health check
2. ✅ Decouple ClickHouse health check
3. ✅ Decouple TimescaleDB health check
4. ✅ Decouple Cassandra health check
5. ✅ Update Settings with env_prefix

**Expected Result**: +4 tests passing

---

### Phase 3: DLQ System (2-3 hours)
1. ✅ Implement schema validation in BaseSink
2. ✅ Add DLQ routing logic
3. ✅ Update DeadLetterEvent model
4. ✅ Create ValidationResult model
5. ✅ Test incompatibility routing

**Expected Result**: +11 tests passing

---

### Phase 4: Schema Evolution (3-4 hours)
1. ✅ Create SchemaMonitor class
2. ✅ Implement schema comparison logic
3. ✅ Add apply_schema_change() to all sinks
4. ✅ Integrate with CDCPipeline
5. ✅ Handle incompatible changes

**Expected Result**: +24 tests passing

---

## Total Effort Estimate

| Phase | Time | Tests Fixed | Cumulative |
|-------|------|-------------|------------|
| Quick Wins | 2h | +8 | 163/199 (82%) |
| Health Checks | 2h | +4 | 167/199 (84%) |
| DLQ System | 3h | +11 | 178/199 (89%) |
| Schema Evolution | 4h | +24 | 199/199 (100%) ✨ |
| **TOTAL** | **11h** | **+47** | **100%** |

---

## Files to Create

1. `src/cdc/schema_monitor.py` - Schema change detection (250 lines)
2. `src/models/validation.py` - ValidationResult model (30 lines)
3. `docs/SCHEMA_EVOLUTION_DESIGN.md` - Design documentation

---

## Files to Modify

### High Priority
1. `src/sinks/base.py` - Add validation + DLQ routing (100 lines added)
2. `src/main.py` - Integrate schema monitoring (50 lines added)
3. `src/transform/masking.py` - Fix defaults (10 lines changed)
4. `src/cdc/offset.py` - Add UPSERT logic (30 lines changed)
5. `tests/conftest.py` - Add ecommerce keyspace (5 lines added)

### Medium Priority
6. `src/observability/health.py` - Decouple health checks (50 lines changed)
7. `src/config/settings.py` - Add env_prefix (20 lines changed)
8. `src/sinks/postgres.py` - Add apply_schema_change() (60 lines added)
9. `src/sinks/clickhouse.py` - Add apply_schema_change() (60 lines added)
10. `src/sinks/timescaledb.py` - Add apply_schema_change() (60 lines added)

### Low Priority
11. `src/models/dead_letter_event.py` - Add schema_details (2 fields)
12. `src/models/event.py` - Verify TTL in create() (verify only)

---

## Testing Strategy

### After Each Phase

```bash
# Phase 1
pytest tests/unit/test_masking.py tests/unit/test_offset_management.py -v

# Phase 2
pytest tests/integration/test_health_checks.py -v

# Phase 3
pytest tests/integration/test_schema_incompatibility.py -v

# Phase 4
pytest tests/integration/test_add_column.py tests/integration/test_alter_type.py tests/integration/test_drop_column.py -v

# Final
pytest tests/ -v
```

---

## Success Criteria

- [ ] All 199 tests passing
- [ ] No skipped or xfailed tests
- [ ] Code coverage ≥ 80%
- [ ] All features documented
- [ ] Integration tests demonstrate end-to-end functionality

---

## Risk Mitigation

### High Risk Items
1. **Schema evolution complexity** - Many edge cases in type conversions
   - Mitigation: Start with simple ADD COLUMN, test thoroughly

2. **DLQ routing performance** - Validation on every event
   - Mitigation: Cache validation results per table schema

3. **Integration test flakiness** - Depends on testcontainers
   - Mitigation: Add retries and better wait conditions

### Rollback Strategy
- Each phase is independent
- Can stop at any phase with partial improvement
- Git commit after each successful phase

---

## Conclusion

All test failures are due to **missing features**, not bugs. The implementation plan is:
- **Well-scoped**: 11 hours total effort
- **Incremental**: Can stop at any phase
- **Documented**: Complete code examples provided
- **Testable**: Clear verification for each phase

**Recommendation**: Implement phases 1-2 for 84% pass rate (4 hours), defer schema evolution if not critical.
