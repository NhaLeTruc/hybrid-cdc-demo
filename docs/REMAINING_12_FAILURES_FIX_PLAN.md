# Implementation Plan: Fix Remaining 12 Test Failures

**Status**: Ready for Implementation
**Date**: 2025-11-20
**Progress**: 187/199 tests passing (93.9%)
**Previous Fix**: Successfully resolved 48 failures by creating 'ecommerce' keyspace

---

## Executive Summary

After fixing the missing 'ecommerce' keyspace issue, 12 test failures remain. These failures fall into three distinct categories requiring different fixes:

1. **Configuration Issue** (1 test) - Missing required field in CassandraSettings initialization
2. **Test Setup Issues** (10 tests) - Missing Postgres table creation in test fixtures
3. **Data Type Issue** (1 test) - Invalid Cassandra tuple literal syntax

---

## Failure Analysis

### Category 1: Configuration Validation Error (1 test)

**File**: [tests/integration/test_cassandra_to_postgres.py:16](tests/integration/test_cassandra_to_postgres.py#L16)

**Test**: `test_insert_event_replicates_to_postgres`

**Error**:
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for CassandraSettings
keyspace
  Field required [type=missing, input_value={}, input_type=dict]
```

**Root Cause**:
- Line 35-37 instantiates `CDCPipeline()` without configuration
- `CassandraSettings.keyspace` is a required field (line 17 in [src/config/settings.py](src/config/settings.py#L17))
- No environment variables or config provided

**Fix Strategy**:
```python
# In test, provide minimal configuration:
from src.config.settings import CDCSettings, CassandraSettings

pipeline = CDCPipeline(
    settings=CDCSettings(
        cassandra=CassandraSettings(
            hosts=[cassandra_container.get_container_host_ip()],
            port=cassandra_container.get_exposed_port(9042),
            keyspace="ecommerce"
        )
    )
)
```

---

### Category 2: Missing Postgres Table Setup (10 tests)

**Affected Tests**:

#### Group A: test_cassandra_to_postgres.py (4 tests)
1. `test_update_event_replicates_to_postgres` - Line 49
2. `test_delete_event_replicates_to_postgres` - Line 82
3. `test_batch_insert_replicates_to_postgres` - Line 109
4. `test_offset_committed_after_replication` - Line 125

#### Group B: test_cassandra_to_timescaledb.py (1 test)
5. `test_insert_event_replicates_to_timescaledb` - Line 16

#### Group C: test_crash_recovery.py (2 tests)
6. `test_resume_from_last_offset_after_crash` - Line 18
7. `test_graceful_shutdown_commits_in_progress_batch` - Line 70

#### Group D: test_exactly_once.py (3 tests)
8. `test_no_duplicates_after_pipeline_restart` - Line 18
9. `test_idempotent_writes_same_event_id` - Line 57
10. `test_offset_prevents_reprocessing` - Line 94

**Errors**:
```
psycopg.errors.UndefinedTable: relation "users" does not exist
psycopg.errors.UndefinedTable: relation "cdc_offsets" does not exist
```

**Root Cause**:
- Tests query Postgres tables (`users`, `cdc_offsets`) that were never created
- Tests create Cassandra tables but assume Postgres tables exist
- No fixture or test setup creates destination Postgres tables

**Fix Strategy**:

**Option A: Extend Fixtures (Recommended)**
Create reusable fixtures in [tests/conftest.py](tests/conftest.py):

```python
@pytest.fixture
async def postgres_users_table(postgres_connection: AsyncConnection):
    """Create users table in Postgres for testing"""
    async with postgres_connection.cursor() as cur:
        await cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id UUID PRIMARY KEY,
                email TEXT,
                phone TEXT,
                first_name TEXT,
                last_name TEXT,
                age INTEGER,
                city TEXT,
                created_at TIMESTAMP
            )
        """)
    await postgres_connection.commit()
    yield
    # Cleanup handled by cleanup_test_data fixture

@pytest.fixture
async def postgres_cdc_offsets_table(postgres_connection: AsyncConnection):
    """Create cdc_offsets table in Postgres for testing"""
    async with postgres_connection.cursor() as cur:
        await cur.execute("""
            CREATE TABLE IF NOT EXISTS cdc_offsets (
                table_name TEXT PRIMARY KEY,
                commitlog_position BIGINT NOT NULL,
                events_replicated_count BIGINT DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    await postgres_connection.commit()
    yield
    # Cleanup handled by cleanup_test_data fixture

@pytest.fixture
async def timescaledb_users_table(timescaledb_connection: AsyncConnection):
    """Create users table in TimescaleDB for testing"""
    async with timescaledb_connection.cursor() as cur:
        await cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id UUID PRIMARY KEY,
                email TEXT,
                phone TEXT,
                first_name TEXT,
                last_name TEXT,
                age INTEGER,
                city TEXT,
                created_at TIMESTAMP
            )
        """)
    await timescaledb_connection.commit()
    yield
    # Cleanup handled by cleanup_test_data fixture
```

**Option B: In-Test Setup**
Add table creation directly in each test (less reusable):

```python
async def test_update_event_replicates_to_postgres(
    self, cassandra_session, postgres_connection, sample_users_table_schema
):
    """Test that UPDATE in Cassandra replicates to Postgres"""
    # Setup Cassandra
    cassandra_session.execute(sample_users_table_schema)

    # Setup Postgres (ADD THIS)
    async with postgres_connection.cursor() as cur:
        await cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id UUID PRIMARY KEY,
                email TEXT,
                first_name TEXT,
                last_name TEXT,
                age INTEGER,
                created_at TIMESTAMP
            )
        """)
    await postgres_connection.commit()

    # ... rest of test
```

**Recommendation**: Use **Option A** (fixtures) for better code reuse and maintainability.

---

### Category 3: Cassandra Tuple Literal Syntax Error (1 test)

**File**: [tests/integration/test_schema_incompatibility.py:163](tests/integration/test_schema_incompatibility.py#L163)

**Test**: `test_tuple_type_incompatibility`

**Error**:
```
cassandra.InvalidRequest: Error from server: code=2200 [Invalid query]
message="Invalid list literal for coordinates of type frozen<tuple<double, double>>"
```

**Root Cause**:
- Line 183 attempts to insert Python tuple: `(id1, (37.7749, -122.4194))`
- Cassandra expects explicit tuple notation in CQL
- Python tuples are automatically converted to lists in the driver

**Fix Strategy**:

The cassandra-driver doesn't automatically handle frozen tuples. Two approaches:

**Approach 1: Use Prepared Statements (Recommended)**
```python
from cassandra.query import tuple_factory

# Insert tuple using prepared statement
prepared = cassandra_session.prepare("""
    INSERT INTO ecommerce.tuple_test (id, coordinates)
    VALUES (?, ?)
""")

# Create a named tuple or use cassandra.util.Tuple
from cassandra.util import Tuple
coordinates = Tuple(37.7749, -122.4194)

cassandra_session.execute(prepared, (id1, coordinates))
```

**Approach 2: Raw CQL String (Simpler)**
```python
# Use explicit tuple notation in CQL
cassandra_session.execute(f"""
    INSERT INTO ecommerce.tuple_test (id, coordinates)
    VALUES ({id1}, (37.7749, -122.4194))
""")
```

**Recommendation**: Use **Approach 1** for type safety and proper parameterization.

---

## Implementation Checklist

### Phase 1: Fix Configuration Issue (Estimated: 15 min)
- [ ] Update `test_insert_event_replicates_to_postgres` to provide CassandraSettings
- [ ] Test fix by running: `pytest tests/integration/test_cassandra_to_postgres.py::TestCassandraToPostgres::test_insert_event_replicates_to_postgres -v`

### Phase 2: Fix Postgres Table Setup Issues (Estimated: 45 min)
- [ ] Add `postgres_users_table` fixture to [tests/conftest.py](tests/conftest.py)
- [ ] Add `postgres_cdc_offsets_table` fixture to [tests/conftest.py](tests/conftest.py)
- [ ] Add `timescaledb_users_table` fixture to [tests/conftest.py](tests/conftest.py)
- [ ] Update test signatures to include new fixtures:
  - [ ] `test_cassandra_to_postgres.py` (4 tests) - add `postgres_users_table`, `postgres_cdc_offsets_table`
  - [ ] `test_cassandra_to_timescaledb.py` (1 test) - add `timescaledb_users_table`
  - [ ] `test_crash_recovery.py` (2 tests) - add `postgres_users_table`, `postgres_cdc_offsets_table`
  - [ ] `test_exactly_once.py` (3 tests) - add `postgres_users_table`, `postgres_cdc_offsets_table`
- [ ] Run affected tests: `pytest tests/integration/test_cassandra_to_postgres.py tests/integration/test_cassandra_to_timescaledb.py tests/integration/test_crash_recovery.py tests/integration/test_exactly_once.py -v`

### Phase 3: Fix Tuple Literal Syntax (Estimated: 10 min)
- [ ] Update `test_tuple_type_incompatibility` to use `cassandra.util.Tuple`
- [ ] Add import: `from cassandra.util import Tuple`
- [ ] Replace line 183 with prepared statement approach
- [ ] Test fix: `pytest tests/integration/test_schema_incompatibility.py::TestSchemaIncompatibility::test_tuple_type_incompatibility -v`

### Phase 4: Verification (Estimated: 10 min)
- [ ] Run full test suite: `pytest tests/ -v`
- [ ] Verify all 199 tests pass
- [ ] Check coverage meets 80% threshold
- [ ] Document final results

---

## Expected Outcomes

**Before Fix**:
- 187 passed, 12 failed (93.9% pass rate)
- Coverage: 48% (below 80% threshold)

**After Fix**:
- 199 passed, 0 failed (100% pass rate) ✅
- Coverage: Expected to remain ~48% (separate concern)

**Coverage Gap**:
The 48% coverage issue is NOT related to test failures. It indicates:
1. Many code paths in `src/` are not executed by tests
2. Need additional test cases for untested modules:
   - `src/observability/tracing.py` (0% coverage)
   - `src/transform/validator.py` (0% coverage)
   - Large portions of sink implementations (18-21% coverage)

Coverage improvement is a **separate initiative** beyond fixing test failures.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| New fixtures break existing tests | Low | Medium | Fixtures are optional (only used when requested) |
| Cassandra tuple handling varies by driver version | Low | Low | Use driver's built-in Tuple class |
| Tests still fail after table creation | Low | Medium | Tests currently have commented assertions - may reveal new issues |
| Coverage stays low | High | Medium | Document as separate improvement track |

---

## Files to Modify

1. **tests/conftest.py** (3 new fixtures)
   - Add `postgres_users_table` fixture
   - Add `postgres_cdc_offsets_table` fixture
   - Add `timescaledb_users_table` fixture

2. **tests/integration/test_cassandra_to_postgres.py** (5 functions)
   - Update `test_insert_event_replicates_to_postgres` - add CassandraSettings config
   - Update 4 test signatures to include fixtures

3. **tests/integration/test_cassandra_to_timescaledb.py** (1 function)
   - Update `test_insert_event_replicates_to_timescaledb` - add fixture

4. **tests/integration/test_crash_recovery.py** (2 functions)
   - Update 2 test signatures to include fixtures

5. **tests/integration/test_exactly_once.py** (3 functions)
   - Update 3 test signatures to include fixtures

6. **tests/integration/test_schema_incompatibility.py** (1 function)
   - Update `test_tuple_type_incompatibility` - fix tuple syntax

---

## Implementation Notes

### Note 1: Test Assertions Are Commented Out
Many integration tests have commented-out assertions (e.g., lines 45-47 in test_cassandra_to_postgres.py):
```python
# assert row is not None
# assert row["email"] == "test@example.com"
```

This suggests these tests are **placeholders** waiting for the actual CDC pipeline implementation. After fixing table setup:
1. Tests will likely pass (no assertions to fail)
2. But tests won't validate actual CDC functionality
3. Future work: Uncomment assertions once CDC pipeline is implemented

### Note 2: CDCPipeline Instantiation
The `CDCPipeline` class is instantiated but never executed:
```python
pipeline = CDCPipeline()
# await pipeline.run_once()  # Commented out
```

This indicates the pipeline implementation is incomplete. For now, we only need to fix the instantiation to not fail validation.

### Note 3: Cleanup Fixture Compatibility
The existing `cleanup_test_data` fixture ([tests/conftest.py:316](tests/conftest.py#L316)) already handles Postgres table cleanup via:
```python
await cur.execute("DROP SCHEMA IF EXISTS public CASCADE;")
await cur.execute("CREATE SCHEMA public;")
```

Our new fixtures will create tables in the `public` schema, and they'll be automatically cleaned up. No additional cleanup needed.

---

## Success Criteria

✅ All 199 tests pass
✅ No test failures in pytest output
✅ Tests complete in <5 minutes
✅ No new warnings introduced
⚠️ Coverage ~48% (separate improvement track)

---

## Next Steps After This Fix

1. **Coverage Improvement** - Increase from 48% to 80%
   - Add unit tests for untested modules
   - Add integration tests for uncommented pipeline flows

2. **Complete CDC Pipeline Implementation**
   - Implement `CDCPipeline.run_once()` method
   - Uncomment test assertions
   - Verify end-to-end replication works

3. **Performance Benchmarking**
   - Run `tests/performance/benchmark_throughput.py`
   - Validate latency requirements

4. **Chaos Testing**
   - Verify resilience tests pass under load
   - Test network partition scenarios

---

## References

- [Test Results Output](../pytest-output.txt) (if saved)
- [CassandraSettings Schema](../src/config/settings.py#L12-L26)
- [Existing Conftest Fixtures](../tests/conftest.py)
- [Cassandra Driver Tuple Docs](https://docs.datastax.com/en/developer/python-driver/latest/api/cassandra/util/#cassandra.util.Tuple)
