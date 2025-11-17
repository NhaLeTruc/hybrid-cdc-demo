# Architecture Research & Design Decisions

**Feature**: Secure Multi-Destination CDC Pipeline
**Date**: 2025-11-17
**Status**: Design Phase Complete

## Overview

This document captures architectural decisions, technology evaluations, and design rationale for the CDC pipeline implementation. All decisions align with project constitution principles, particularly Security-First Architecture, Multi-Database Compatibility, Exactly-Once Semantics, and Test-Driven Development.

## ADR-001: Language & Runtime Selection

**Decision**: Python 3.11+ with asyncio for concurrent I/O

**Rationale**:
- **Ecosystem**: Python dominates data engineering with mature drivers for all target databases (cassandra-driver, psycopg, clickhouse-driver)
- **Async I/O**: asyncio native support for non-blocking I/O critical for concurrent multi-destination writes without thread overhead
- **Observability**: First-class libraries (structlog, prometheus-client, opentelemetry) align with constitution observability requirements
- **TDD**: pytest ecosystem (testcontainers, pytest-asyncio, pytest-mock) enables comprehensive testing
- **Type safety**: Python 3.11+ with mypy provides optional static typing for critical paths

**Alternatives Considered**:
- **Go**: Superior performance, better concurrency primitives, but weaker testing ecosystem for multi-database integration (testcontainers support limited)
- **Java/Scala**: JVM ecosystem strong for CDC (Debezium), but heavier resource footprint (conflicts with <512MB memory constraint) and slower iteration
- **Rust**: Best performance and safety, but steep learning curve and immature CDC libraries (cassandra-cpp bindings unstable)

**Trade-offs Accepted**:
- Python GIL limits true parallelism → mitigated by asyncio I/O concurrency (CPU not bottleneck for I/O-bound CDC)
- Slower raw performance vs Go/Rust → acceptable for 1K events/sec target (well within Python asyncio capabilities)

## ADR-002: CDC Implementation Strategy

**Decision**: Custom Cassandra commitlog reader (not Debezium/Kafka)

**Rationale**:
- **Simplicity**: Constitution Principle VII (Simplicity) - avoid heavyweight Kafka/Debezium infrastructure for demo scope
- **Control**: Direct commitlog reading provides full control over offset management, masking at source, and exactly-once semantics
- **Dependencies**: Minimizes external dependencies (no Kafka cluster, no Debezium connectors)
- **Demo focus**: Demonstrates CDC concepts without obscuring logic behind framework abstractions

**Alternatives Considered**:
- **Debezium + Kafka**: Industry-standard CDC stack, but adds operational complexity (Kafka cluster, Zookeeper, connector management), violates YAGNI for demo
- **Cassandra DSE CDC**: DataStax Enterprise CDC features, but requires proprietary DSE license (not open-source)
- **Trigger-based**: Cassandra triggers write to audit table, but degrades source database performance and lacks native CDC timestamp/offset tracking

**Implementation Notes**:
- Cassandra 4.x CDC enabled via `cdc_enabled: true` on tables
- Commitlog files in `$CASSANDRA_HOME/data/cdc_raw/` directory
- Parse commitlog binary format using cassandra-driver `CommitLog` reader (if available) or custom binary parser
- Track offset as `(commitlog_file, position)` tuple

## ADR-003: Exactly-Once Semantics Approach

**Decision**: Transactional offset commits with idempotent sink operations

**Rationale**:
- **Offset atomicity**: Store replication offset in same Postgres transaction as data write → offset committed IFF data committed
- **Idempotent sinks**: UPSERT semantics (ON CONFLICT UPDATE) ensure replayed events don't create duplicates
- **Deduplication**: Event identity based on `(table, partition_key, clustering_key, timestamp)` ensures natural deduplication

**Alternatives Considered**:
- **Two-phase commit (2PC)**: True distributed transactions across 3 warehouses, but complex, slow, and brittle (coordinator SPOF)
- **At-least-once + dedup**: Simpler but requires complex deduplication logic at query time
- **Kafka-style offsets**: External offset storage (Kafka-style), but adds dependency and coordination overhead

**Per-Destination Strategy**:
- **Postgres**: `INSERT ... ON CONFLICT (partition_key, clustering_key) DO UPDATE SET ...` with offset in metadata table within same transaction
- **ClickHouse**: `ReplacingMergeTree` engine with `ver` column (timestamp) for automatic deduplication + separate offset table
- **TimescaleDB**: Same as Postgres (TimescaleDB is Postgres extension, full ACID support)

**Trade-offs**:
- Offset stored in Postgres only (not all 3 warehouses) → if Postgres dies, must replay from last known offset in ClickHouse/TimescaleDB (acceptablefor demo)
- ClickHouse eventual deduplication (merge happens async) → recent duplicates possible until merge completes

## ADR-004: PII/PHI Masking Strategy

**Decision**: SHA-256 hashing for PII, HMAC tokenization for PHI

**Rationale**:
- **PII (email, phone, SSN)**: Irreversible SHA-256 hash → cannot recover original, satisfies GDPR right-to-erasure (hash survives, but useless without original)
- **PHI (medical_record_number, diagnosis)**: HMAC with secret key → deterministic (same value → same token for analytics) but reversible if key leaked (requires key rotation policies)
- **Performance**: SHA-256 and HMAC are fast (thousands per second), no external token vault needed for demo

**Alternatives Considered**:
- **Full encryption (AES)**: Reversible but requires key management, wider attack surface, not appropriate for analytics (can't aggregate encrypted data)
- **Format-preserving encryption (FPE)**: Preserves data type (e.g., email looks like email), but complex and slower
- **External token vault**: Centralized tokenization service, adds network latency and SPOF, overkill for demo

**Implementation**:
- Masking happens in `src/transform/masking.py` BEFORE sink writes
- Configuration in `config/masking-rules.yaml` defines field classifications
- Audit log records which fields were masked in each event

**Compliance Notes**:
- GDPR: Hashed PII is pseudonymous data (still regulated), but immutability acceptable for demo
- HIPAA: HMAC PHI with key rotation satisfies "de-identification" for analytics

## ADR-005: Multi-Destination Sink Architecture

**Decision**: Abstract sink interface with per-database implementations

**Rationale**:
- **Pluggability**: `BaseSink` ABC defines `write_batch(events)`, `commit_offset(offset)` → new destinations add new subclass
- **Parallel writes**: Asyncio concurrent tasks write to all 3 warehouses in parallel (no sequential blocking)
- **Independent failure handling**: Slow/failing ClickHouse doesn't block Postgres/TimescaleDB writes
- **Constitution alignment**: Principle II (Multi-Database Compatibility) requires abstraction layers

**Sink Interface**:
```python
class BaseSink(ABC):
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def write_batch(self, events: List[ChangeEvent]) -> None: ...

    @abstractmethod
    async def commit_offset(self, offset: ReplicationOffset) -> None: ...

    @abstractmethod
    async def health_check(self) -> bool: ...
```

**Implementations**:
- `PostgresSink`: psycopg3 async driver, INSERT ... ON CONFLICT, offset in `_cdc_offsets` table
- `ClickHouseSink`: clickhouse-driver (sync, wrapped in asyncio executor), INSERT into ReplacingMergeTree
- `TimescaleDBSink`: Inherits from PostgresSink (TimescaleDB is Postgres extension, same protocol)

**Backpressure Handling**:
- Asyncio `Semaphore(max_in_flight_batches)` limits concurrent writes per sink
- If sink semaphore saturated, reader pauses until write slots available
- Prevents unbounded memory growth during slow destination scenarios

## ADR-006: Observability Stack

**Decision**: Prometheus metrics + structlog JSON logging + OpenTelemetry tracing

**Rationale**:
- **Metrics**: Prometheus is industry standard for time-series monitoring, integrates with Grafana, simple /metrics HTTP endpoint
- **Logging**: structlog provides structured JSON logging with correlation IDs, machine-readable for log aggregation (ELK, Loki)
- **Tracing**: OpenTelemetry provides vendor-neutral distributed tracing (spans for read→mask→write flow)
- **Constitution**: Principle IV (Observable & Debuggable Systems) mandates metrics, logs, traces

**Key Metrics** (align with spec Success Criteria):
- `cdc_events_processed_total{destination, table}`: Counter for total events replicated
- `cdc_replication_lag_seconds{destination}`: Gauge for seconds behind Cassandra
- `cdc_events_per_second{destination}`: Gauge for throughput
- `cdc_errors_total{destination, error_type}`: Counter for errors by type
- `cdc_backlog_depth{destination}`: Gauge for uncommitted events

**Logging Format**:
```json
{
  "timestamp": "2025-11-17T10:30:45.123Z",
  "level": "info",
  "event": "event_replicated",
  "correlation_id": "uuid-1234",
  "table": "users",
  "partition_key": "user_123",
  "destination": "postgres",
  "masked_fields": ["email", "ssn"],
  "duration_ms": 45
}
```

**Tracing Spans**:
- `cdc.read_event`: Reading from Cassandra commitlog
- `cdc.mask_event`: Applying PII/PHI masking
- `cdc.write_postgres`: Writing to Postgres sink
- `cdc.write_clickhouse`: Writing to ClickHouse sink
- `cdc.write_timescaledb`: Writing to TimescaleDB sink

## ADR-007: Testing Strategy

**Decision**: Pytest + Testcontainers + Toxiproxy for comprehensive testing

**Rationale**:
- **Unit tests**: Pytest for fast, isolated tests of masking, type mapping, offset logic (80%+ coverage)
- **Integration tests**: Testcontainers-python spins up real Cassandra, Postgres, ClickHouse, TimescaleDB in Docker → tests against actual databases
- **Chaos tests**: Toxiproxy injects network failures (latency, partitions, timeouts) to validate retry/recovery logic
- **Contract tests**: JSON schema validation ensures event format stability
- **Constitution**: Principle V (TDD NON-NEGOTIABLE) requires Red-Green-Refactor workflow

**Testcontainers Setup**:
```python
# conftest.py
@pytest.fixture(scope="session")
def cassandra_container():
    with CassandraContainer("cassandra:4.1") as cassandra:
        cassandra.with_env("JVM_OPTS", "-Dcassandra.cdc.enabled=true")
        yield cassandra

@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:15-alpine") as postgres:
        yield postgres

@pytest.fixture(scope="session")
def clickhouse_container():
    with GenericContainer("clickhouse/clickhouse-server:23-alpine") as clickhouse:
        yield clickhouse
```

**Test Categories**:
- `tests/unit/`: Fast, no I/O, mock external dependencies
- `tests/integration/`: Testcontainers, full end-to-end replication
- `tests/contract/`: Schema validation (event, offset, config formats)
- `tests/chaos/`: Toxiproxy fault injection (network partition, slow destination)
- `tests/performance/`: Benchmark throughput, latency under load

**CI Pipeline**:
- Pre-commit: black (formatting), mypy (type checking), ruff (linting)
- Unit tests: Fast feedback (<30s), run on every commit
- Integration tests: Run on PR, ~5 minutes (Docker startup overhead)
- Chaos tests: Run nightly or on-demand (long-running)
- Performance tests: Run weekly, compare to baseline

## ADR-008: Configuration Management

**Decision**: YAML files + Pydantic models + environment variables

**Rationale**:
- **YAML**: Human-readable for masking rules, schema mappings (declarative configuration)
- **Pydantic**: Type-safe validation, auto-generates docs, catches config errors at startup
- **Env vars**: Secrets (credentials) via environment variables (12-factor app), never in version control
- **Constitution**: Principle VII (Configuration over code) mandates externalized tunables

**Configuration Files**:
- `config/pipeline.yaml`: Core settings (batch size, parallelism, retry policy)
- `config/masking-rules.yaml`: PII/PHI field classifications per table
- `config/schema-mappings.yaml`: Cassandra → warehouse type mappings
- `.env` (local only, .gitignored): Database credentials, secrets

**Pydantic Models**:
```python
class PipelineSettings(BaseSettings):
    cassandra_hosts: List[str]
    cassandra_keyspace: str
    batch_size: int = 100
    max_parallelism: int = 4
    retry_max_attempts: int = 5
    retry_backoff_multiplier: float = 2.0

    class Config:
        env_prefix = "CDC_"  # CDC_CASSANDRA_HOSTS, CDC_BATCH_SIZE, etc.
```

**Secrets Handling**:
- Local dev: `python-dotenv` loads from `.env` file
- Production: Environment variables injected by orchestrator (Kubernetes secrets, AWS ECS task definition)
- Optional: `hvac` library for HashiCorp Vault integration (fetch secrets dynamically)

## ADR-009: Schema Mapping Strategy

**Decision**: Declarative YAML mapping with runtime validation

**Rationale**:
- **Type safety**: Map Cassandra CQL types to Postgres/ClickHouse/TimescaleDB SQL types explicitly
- **Validation**: Pytest contract tests validate mappings preserve semantics (no precision loss)
- **Flexibility**: YAML allows per-table custom mappings without code changes

**Example Mapping**:
```yaml
# config/schema-mappings.yaml
tables:
  users:
    cassandra_to_postgres:
      id: "UUID → uuid"
      email: "TEXT → varchar(255)"
      created_at: "TIMESTAMP → timestamptz"
      age: "INT → integer"
    cassandra_to_clickhouse:
      id: "UUID → UUID"
      email: "TEXT → String"
      created_at: "TIMESTAMP → DateTime64(3)"
      age: "INT → Int32"
    cassandra_to_timescaledb:
      # Inherits from cassandra_to_postgres (TimescaleDB is Postgres)
```

**Complex Type Handling**:
- **Cassandra MAP → Postgres JSONB**: Serialize MAP to JSON string
- **Cassandra SET → Postgres ARRAY**: Direct mapping for primitive types, JSON for complex
- **Cassandra UDT → JSON**: User-defined types serialized to JSON for all warehouses
- **Unsupported types**: Route to DLQ with clear error message (per spec edge case handling)

## ADR-010: Local Development & Testing Setup

**Decision**: Docker Compose for local multi-database stack

**Rationale**:
- **Consistency**: Developers run identical database versions as CI/production
- **Simplicity**: Single `docker-compose up` starts Cassandra + Postgres + ClickHouse + TimescaleDB
- **TDD enablement**: Fast local iteration with realistic database backends

**Docker Compose Services**:
```yaml
services:
  cassandra:
    image: cassandra:4.1
    environment:
      - CASSANDRA_CDC_ENABLED=true
    ports:
      - "9042:9042"
    volumes:
      - ./docker/cassandra-init.cql:/docker-entrypoint-initdb.d/init.cql

  postgres:
    image: postgres:15-alpine
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_PASSWORD=postgres

  clickhouse:
    image: clickhouse/clickhouse-server:23-alpine
    ports:
      - "8123:8123"  # HTTP interface
      - "9000:9000"  # Native protocol

  timescaledb:
    image: timescale/timescaledb:2.13-pg15
    ports:
      - "5433:5432"  # Different port to avoid conflict with postgres
    environment:
      - POSTGRES_PASSWORD=postgres
```

**Setup Scripts**:
- `scripts/setup-local-env.sh`: Create tables, enable CDC, seed test data
- `scripts/seed-test-data.sh`: Insert 1000 sample records (users, orders, events tables)
- `scripts/run-integration-tests.sh`: Start Docker Compose, run tests, tear down

**Developer Workflow**:
1. `docker-compose up -d` (start databases)
2. `./scripts/setup-local-env.sh` (initialize schemas, seed data)
3. `pytest tests/unit/` (fast tests, no Docker)
4. `pytest tests/integration/` (full end-to-end with Docker databases)
5. `python src/main.py` (run pipeline locally)

## ADR-011: Retry & Failure Handling

**Decision**: Exponential backoff with jitter + dead letter queue

**Rationale**:
- **Transient failures**: Network blips, connection pool exhaustion → exponential backoff with jitter avoids thundering herd
- **Permanent failures**: Schema incompatibility, type mismatch → route to DLQ after max retries (don't block pipeline)
- **Per-destination independence**: Failing ClickHouse doesn't block Postgres writes → separate retry loops per sink

**Retry Policy** (configurable):
```python
retry_config = {
    "max_attempts": 5,
    "base_delay_ms": 100,
    "max_delay_ms": 30000,
    "backoff_multiplier": 2.0,
    "jitter": True  # Add random 0-25% jitter to avoid thundering herd
}
```

**Retry Logic**:
```python
async def write_with_retry(sink, batch):
    for attempt in range(1, max_attempts + 1):
        try:
            await sink.write_batch(batch)
            return  # Success
        except TransientError as e:
            if attempt == max_attempts:
                await dlq.write(batch, error=e)
                break
            delay = min(base_delay * (multiplier ** (attempt - 1)), max_delay)
            delay *= (1 + random.uniform(0, 0.25))  # Jitter
            await asyncio.sleep(delay / 1000)
        except PermanentError as e:
            await dlq.write(batch, error=e)
            break  # Don't retry permanent errors
```

**Dead Letter Queue**:
- **Format**: JSONL file (one JSON object per line) with failed event + error context
- **Location**: `data/dlq/failed_events_YYYY-MM-DD.jsonl`
- **Schema**: `{event, error, stacktrace, timestamp, retry_count, destination}`
- **Recovery**: Manual inspection, fix issue (schema, config), replay from DLQ

## ADR-012: Deployment Strategy

**Decision**: Docker container with environment-based configuration

**Rationale**:
- **Portability**: Docker image runs anywhere (local, EC2, Kubernetes, Cloud Run)
- **Immutability**: Bake code into image, inject config via env vars at runtime
- **Simplicity**: Single `docker run` command for deployment, aligns with constitution simplicity principle

**Dockerfile** (multi-stage build):
```dockerfile
# Stage 1: Build dependencies
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY src/ ./src/
COPY config/ ./config/
ENV PATH=/root/.local/bin:$PATH
CMD ["python", "-m", "src.main"]
```

**Deployment Options**:
- **Local**: `docker-compose.yml` includes pipeline service
- **Cloud VM**: `docker run` with env vars from cloud secrets manager
- **Kubernetes**: Deployment + ConfigMap (config files) + Secret (credentials)
- **AWS ECS/Fargate**: Task definition with environment variables

## Summary & Next Steps

All architectural decisions documented and aligned with project constitution:
- ✅ Security-First: TLS, masking, audit logs, secrets management
- ✅ Multi-Database: Pluggable sinks, declarative schema mappings
- ✅ Exactly-Once: Transactional offsets, idempotent sinks
- ✅ Observable: Prometheus, structlog, OpenTelemetry
- ✅ TDD: Pytest, testcontainers, chaos testing
- ✅ Performance: Asyncio, batching, backpressure
- ✅ Simplicity: Minimal dependencies, configuration over code

**Phase 1 Deliverables** (next):
- `data-model.md`: Entity definitions with fields, relationships, validations
- `contracts/`: Schemas for config, events, offsets, metrics API
- `quickstart.md`: 10-minute guide from clone to running pipeline

**Ready for**: Implementation task breakdown (`/speckit.tasks`)
