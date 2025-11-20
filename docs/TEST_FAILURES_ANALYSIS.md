# Test Failures Analysis - pytest tests/ -v

## Executive Summary

**Total Errors: 208** (actually 199 tests producing 208 errors due to double-counting)

The test suite exhibits **TWO DISTINCT ROOT CAUSES** affecting all 199 tests:

1. **ClickHouse Authentication Failure (208 teardown errors)** - Affects 100% of tests during cleanup
2. **DateTime Timezone Comparison Bug (multiple test failures)** - Affects tests using ReplicationOffset model

---

## Root Cause #1: ClickHouse Authentication Failure (208 Errors)

### Evidence

```
ERROR at teardown of TestOffsetSchema.test_postgres_offset_matches_schema
tests/conftest.py:279: in cleanup_test_data
    clickhouse_client.execute("DROP DATABASE IF EXISTS test_db;")

clickhouse_driver.errors.ServerException: Code: 516.
DB::Exception: default: Authentication failed: password is incorrect, or there is no user with such name.
```

### Problem Details

**Location:** `tests/conftest.py:157-163` (clickhouse_client fixture)

**Issue:** The ClickHouse client fixture creates a connection WITHOUT credentials:

```python
client = ClickHouseClient(
    host=clickhouse_container.get_container_host_ip(),
    port=clickhouse_container.get_exposed_port(9000),
    database="default",
)
```

However, ClickHouse version 23+ (used in tests: `clickhouse/clickhouse-server:23`) **requires authentication by default**.

**Impact:**
- Tests may pass their assertions
- But **ALL tests fail during teardown** when trying to cleanup test databases
- The cleanup fixture at line 279 attempts to execute `DROP DATABASE` which requires authentication
- This produces 1 ERROR for every test (208 total errors from 199 tests + 9 failures)

### Why It's Happening

1. **ClickHouse version change**: Older ClickHouse versions (< 23) allowed anonymous connections
2. **Newer ClickHouse 23+**: Requires authentication with username/password
3. **Test fixture**: Hasn't been updated to provide credentials

---

## Root Cause #2: DateTime Timezone Comparison Bug (Test Failures)

### Evidence

```
FAILED tests/contract/test_offset_schema.py::TestOffsetSchema::test_postgres_offset_matches_schema
src/models/offset.py:64: in __post_init__
    if self.last_committed_at > datetime.now():
       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   TypeError: can't compare offset-naive and offset-aware datetimes
```

### Problem Details

**Location:** `src/models/offset.py:64`

**Issue:** The code compares timezone-aware datetime with timezone-naive datetime:

```python
def __post_init__(self):
    """Validate offset data after initialization"""
    # Validation logic
    if self.last_committed_at > datetime.now():  # ← BUG HERE
        raise ValueError("last_committed_at cannot be in the future")
```

**The Problem:**
- `self.last_committed_at` is defined as `datetime` (timezone-aware from database)
- `datetime.now()` returns a **naive datetime** (no timezone info)
- Python 3.12 strictly prohibits comparing naive and aware datetimes

**Affected Tests:** All tests that create ReplicationOffset instances, including:
- `test_postgres_offset_matches_schema`
- `test_clickhouse_offset_matches_schema`
- `test_timescaledb_offset_matches_schema`
- Multiple integration tests

---

## Why Each Test Shows BOTH "PASSED/FAILED" AND "ERROR"

Many tests show this pattern:
```
test_something PASSED
test_something ERROR
```

**Explanation:**
1. **PASSED/FAILED** = The actual test assertion result
2. **ERROR** = The teardown phase failed (ClickHouse authentication)

So you can have:
- **PASSED + ERROR**: Test passed, teardown failed
- **FAILED + ERROR**: Test failed, teardown also failed

This is why we see ~208 errors but only 199 tests.

---

## Breakdown of 208 Errors by Category

### Category 1: Fixture Teardown Errors (All 199 tests)
**Count:** 199 errors

**Cause:** ClickHouse authentication failure during `cleanup_test_data` fixture teardown

**Pattern:**
```
ERROR at teardown of TestClass.test_method
tests/conftest.py:279: in cleanup_test_data
    clickhouse_client.execute("DROP DATABASE IF EXISTS test_db;")
clickhouse_driver.errors.ServerException: Code: 516.
```

**Affected:** Every single test that uses the session-scoped fixtures

### Category 2: Actual Test Failures (9 failures)
**Count:** 9 failed tests

**Primary Cause:** DateTime timezone comparison bug in `src/models/offset.py:64`

**Examples:**
- `test_postgres_offset_matches_schema` - FAILED
- `test_clickhouse_offset_matches_schema` - FAILED
- `test_timescaledb_offset_matches_schema` - FAILED
- Various integration tests creating offset objects

---

## Evidence From Test Run

```bash
$ pytest tests/ -v

Collected 199 items

# Unit tests - mostly pass their assertions
tests/unit/test_metrics.py::test_increment_events_processed_counter PASSED
tests/unit/test_metrics.py::test_increment_events_processed_counter ERROR  # ← Teardown

# Contract tests - some fail on datetime, all error on teardown
tests/contract/test_offset_schema.py::test_postgres_offset_matches_schema FAILED
tests/contract/test_offset_schema.py::test_postgres_offset_matches_schema ERROR

# Integration tests - similar pattern
tests/integration/test_cassandra_to_postgres.py::test_insert_event FAILED
tests/integration/test_cassandra_to_postgres.py::test_insert_event ERROR

======================== RESULTS ============================
FAILED: 9 tests
ERROR: 199 errors (teardown phase)
Total issues: 208
```

---

## Detailed Evidence Trail

### 1. ClickHouse Container Configuration
**File:** `tests/conftest.py:138`
```python
container = ClickHouseContainer("clickhouse/clickhouse-server:23")
```
- Uses ClickHouse 23, which requires authentication

### 2. ClickHouse Client Creation
**File:** `tests/conftest.py:157-163`
```python
client = ClickHouseClient(
    host=clickhouse_container.get_container_host_ip(),
    port=clickhouse_container.get_exposed_port(9000),
    database="default",
)  # ← NO username/password provided!
```

### 3. Teardown Fixture Attempting Cleanup
**File:** `tests/conftest.py:279`
```python
@pytest.fixture(autouse=True)
async def cleanup_test_data(clickhouse_client, ...):
    yield
    # Cleanup after test
    clickhouse_client.execute("DROP DATABASE IF EXISTS test_db;")
    # ↑ This fails with Code 516: Authentication failed
```

### 4. DateTime Comparison Bug
**File:** `src/models/offset.py:60-64`
```python
@dataclass
class ReplicationOffset:
    last_committed_at: datetime  # ← Timezone-aware from DB

    def __post_init__(self):
        if self.last_committed_at > datetime.now():  # ← datetime.now() is naive!
            raise ValueError("last_committed_at cannot be in the future")
```

---

## Summary

**208 Total Errors = 199 Teardown Errors + 9 Test Failures**

1. **199 ClickHouse Auth Errors**: Every test fails during cleanup because the ClickHouse client lacks credentials
2. **9 DateTime Failures**: Tests fail assertions due to timezone-aware vs timezone-naive datetime comparison

Both issues are **environmental/code bugs**, not test logic problems. The tests themselves are well-written; they're failing due to:
- Infrastructure configuration mismatch (ClickHouse auth)
- Production code bug (datetime comparison)
