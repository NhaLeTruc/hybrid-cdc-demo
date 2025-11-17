# Implementation Plan: Secure Multi-Destination CDC Pipeline

**Branch**: `001-secure-cdc-pipeline` | **Date**: 2025-11-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-secure-cdc-pipeline/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a production-grade change data capture (CDC) pipeline that replicates data changes from Apache Cassandra to three data warehouse destinations (Postgres, ClickHouse, TimescaleDB) with exactly-once delivery semantics, PII/PHI masking for regulatory compliance, comprehensive observability (metrics, logs, traces), automatic failure recovery, and graceful schema evolution handling. The system prioritizes security-first architecture and test-driven development as mandated by the project constitution.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- **CDC/Streaming**: cassandra-driver (Cassandra client), custom CDC reader
- **Database Drivers**: psycopg[binary] (Postgres), clickhouse-driver (ClickHouse), psycopg (TimescaleDB via Postgres wire protocol)
- **Observability**: prometheus-client (metrics), structlog (JSON logging), opentelemetry-api + opentelemetry-sdk (distributed tracing)
- **Security**: cryptography (hashing), python-dotenv (local secrets), hvac (HashiCorp Vault client - optional)
- **Configuration**: pydantic-settings (config validation), PyYAML (config files)
- **Async/Concurrency**: asyncio (async I/O), aiohttp (async HTTP for health checks)

**Storage**:
- Source: Apache Cassandra 4.x (CDC commitlog)
- Destinations: Postgres 15+, ClickHouse 23+, TimescaleDB 2.13+ (Postgres extension)
- Offset storage: Postgres metadata table or local SQLite (fallback)
- Dead letter queue: Append-only JSONL file or Postgres table

**Testing**:
- **Unit**: pytest, pytest-asyncio, pytest-cov (coverage), pytest-mock
- **Integration**: testcontainers-python (Docker-based database testing), docker-compose (multi-container orchestration)
- **Contract**: pytest with schema validation fixtures
- **Chaos**: toxiproxy-python (network failure simulation), custom partition/failure injection
- **Performance**: locust (load testing) or custom benchmarking scripts

**Target Platform**: Linux x86_64/ARM64 (Docker containers), macOS/Windows via Docker Desktop for local development

**Project Type**: Single pipeline application (data engineering service)

**Performance Goals**:
- Throughput: 1,000 events/sec sustained, 10,000 events/sec burst
- Latency: p99 replication lag < 5 seconds under normal load
- Startup time: < 30 seconds cold start to active replication

**Constraints**:
- Memory: < 512MB per pipeline instance under normal load
- CPU: < 2 cores per instance for 1K events/sec
- Exactly-once semantics (no data loss, no duplicates)
- PII/PHI masking before network transmission (regulatory compliance)

**Scale/Scope**:
- 1-3 Cassandra tables monitored per pipeline instance
- 3 destination warehouses per pipeline instance
- 10-100 partitions per Cassandra table
- Demo scope: ~100K total events over 24-hour test run

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Security-First Architecture (NON-NEGOTIABLE) ✅

- **Encryption**: TLS 1.3+ for all database connections (Cassandra, Postgres, ClickHouse, TimescaleDB)
- **Data masking**: PII/PHI fields masked via SHA-256 hashing or HMAC-based tokenization before warehouse writes
- **Least privilege**: Database users have read-only on Cassandra, write-only on destinations
- **Audit logging**: All change events logged with correlation IDs, timestamps, masked/unmasked field indicators
- **Secrets management**: Credentials loaded from environment variables (local: .env, production: Vault/AWS Secrets Manager)
- **Security scanning**: Automated with Snyk/Dependabot (GitHub Actions), pre-commit hooks for basic checks

**Status**: PASS - Architecture designed with security as foundational layer

### II. Multi-Database Compatibility ✅

- **Abstraction layers**: CDC reader (Cassandra-specific) → Event processor (generic) → Sink writers (destination-specific)
- **Schema mapping**: Declarative YAML config mapping Cassandra types to Postgres/ClickHouse/TimescaleDB types
- **Pluggable connectors**: Sink interface with implementations for each warehouse; new sinks add new class
- **Type validation**: Pytest fixtures validate type conversions preserve semantics (timestamps, decimals, UUIDs, etc.)

**Status**: PASS - Pluggable architecture supports adding new sources/destinations

### III. Exactly-Once Delivery Semantics ✅

- **Idempotent operations**: UPSERT semantics for all sinks (INSERT ... ON CONFLICT UPDATE for Postgres, ReplacingMergeTree for ClickHouse)
- **Offset management**: Atomic offset commits in Postgres transaction with data writes (two-phase commit simulation)
- **Deduplication**: Event dedup based on (table, partition_key, clustering_key, timestamp) tuple
- **Failure recovery**: Offset read on startup, resume from last committed position

**Status**: PASS - Transactional offset management ensures exactly-once

### IV. Observable & Debuggable Systems ✅

- **Structured logging**: structlog with JSON formatter, correlation IDs, severity levels, table/partition context
- **Metrics**: Prometheus endpoint (/metrics) exposing:
  - `cdc_events_processed_total{destination, table}` (counter)
  - `cdc_replication_lag_seconds{destination}` (gauge)
  - `cdc_events_per_second{destination}` (gauge, rate)
  - `cdc_errors_total{destination, error_type}` (counter)
  - `cdc_backlog_depth{destination}` (gauge)
- **Tracing**: OpenTelemetry spans for event capture → transform → sink path
- **Health checks**: /health endpoint with dependency checks (Cassandra up, warehouses reachable)
- **Dead letter queue**: Failed events written to DLQ with full payload, error, stack trace

**Status**: PASS - Comprehensive observability built-in

### V. Test-Driven Development (NON-NEGOTIABLE) ✅

- **Unit tests**: 80%+ coverage for masking, type mapping, offset management, retry logic
- **Integration tests**: Testcontainers spin up Cassandra + Postgres + ClickHouse + TimescaleDB, verify end-to-end replication
- **Chaos tests**: Toxiproxy simulates network partitions, slow destinations, connection drops
- **Performance tests**: Locust or custom benchmarks validate 1K events/sec throughput, <5s p99 lag
- **Schema evolution tests**: Fixtures test ADD/DROP/ALTER column scenarios
- **Compliance tests**: Assertions verify PII/PHI fields are masked in destination queries

**Workflow**: Tests written first (Red), implementation (Green), refactor (Refactor)

**Status**: PASS - TDD enforced via pytest, testcontainers for realistic testing

### VI. Performance & Scalability ✅

- **Batch processing**: Configurable micro-batching (default 100 events per batch, tunable 10-1000)
- **Parallel processing**: asyncio concurrent workers per Cassandra partition (configurable parallelism)
- **Backpressure handling**: Asyncio semaphores limit in-flight batches; slow destinations don't block fast ones
- **Resource limits**: Configured via environment (max memory, connection pool sizes)
- **Benchmarking**: Performance tests establish baseline (documented in quickstart.md)

**Status**: PASS - Async architecture with configurable tuning

### VII. Simplicity & Maintainability ✅

- **YAGNI**: No premature abstraction; single CDC implementation, add abstraction when second source needed
- **Dependency minimization**: Core deps only (drivers, logging, metrics); avoid heavyweight frameworks
- **Configuration over code**: All tunables in YAML config or env vars (batch size, parallelism, retry params)
- **Documentation**: ADRs in specs/001-secure-cdc-pipeline/research.md, quickstart under 10 minutes
- **Code clarity**: Type hints (mypy), docstrings, inline comments for complex logic

**Status**: PASS - Simple, focused implementation without over-engineering

### Security & Compliance Requirements ✅

- **PII fields**: email, phone, ssn, address → SHA-256 hashed
- **PHI fields**: medical_record_number, diagnosis → HMAC tokenization with secret key
- **GDPR**: Tombstone events (deletes) propagated to warehouses
- **HIPAA**: Audit logs include all PHI access, TLS for all connections
- **Vulnerability management**: Dependabot daily scans, Snyk CI integration

**Status**: PASS - Compliance baked into design

### Operational Excellence Standards ✅

- **Infrastructure as Code**: docker-compose.yml for local dev, Dockerfile for production
- **Monitoring**: Prometheus scraping /metrics, Grafana dashboard template (optional)
- **DR**: Offset backups via Postgres replication (warehouse DB already backed up)

**Status**: PASS - Docker-first deployment with monitoring hooks

## Project Structure

### Documentation (this feature)

```text
specs/001-secure-cdc-pipeline/
├── plan.md              # This file (/speckit.plan command output)
├── spec.md              # Feature specification (already created)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── config-schema.yaml       # Configuration file schema
│   ├── event-schema.json        # CDC event JSON schema
│   ├── offset-schema.json       # Offset storage schema
│   └── metrics-api.yaml         # Prometheus metrics specification
├── checklists/
│   └── requirements.md  # Spec quality checklist (already created)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created yet)
```

### Source Code (repository root)

```text
src/
├── cdc/
│   ├── __init__.py
│   ├── reader.py           # Cassandra CDC commitlog reader
│   ├── parser.py           # Parse CDC events from commitlog
│   └── offset.py           # Offset management (read/write/commit)
├── transform/
│   ├── __init__.py
│   ├── masking.py          # PII/PHI masking (hash, tokenize)
│   ├── schema_mapper.py    # Cassandra → warehouse type mapping
│   └── validator.py        # Event validation
├── sinks/
│   ├── __init__.py
│   ├── base.py             # Abstract sink interface
│   ├── postgres.py         # Postgres sink implementation
│   ├── clickhouse.py       # ClickHouse sink implementation
│   └── timescaledb.py      # TimescaleDB sink implementation
├── observability/
│   ├── __init__.py
│   ├── metrics.py          # Prometheus metrics
│   ├── logging.py          # Structlog configuration
│   └── tracing.py          # OpenTelemetry setup
├── config/
│   ├── __init__.py
│   ├── settings.py         # Pydantic settings models
│   └── loader.py           # Config file loader (YAML)
├── models/
│   ├── __init__.py
│   ├── event.py            # ChangeEvent dataclass
│   ├── offset.py           # ReplicationOffset dataclass
│   └── schema.py           # SchemaVersion dataclass
├── dlq/
│   ├── __init__.py
│   └── writer.py           # Dead letter queue writer
└── main.py                 # Pipeline entrypoint

tests/
├── unit/
│   ├── test_masking.py
│   ├── test_schema_mapper.py
│   ├── test_offset.py
│   ├── test_retry_logic.py
│   └── test_config.py
├── integration/
│   ├── test_cassandra_to_postgres.py
│   ├── test_cassandra_to_clickhouse.py
│   ├── test_cassandra_to_timescaledb.py
│   ├── test_exactly_once.py
│   └── test_crash_recovery.py
├── contract/
│   ├── test_event_schema.py
│   ├── test_config_schema.py
│   └── test_type_conversions.py
├── chaos/
│   ├── test_network_partition.py
│   ├── test_slow_destination.py
│   └── test_database_restart.py
├── performance/
│   └── benchmark_throughput.py
└── conftest.py             # Pytest fixtures (testcontainers setup)

docker/
├── Dockerfile              # Production pipeline image
├── Dockerfile.dev          # Development image with test deps
└── docker-compose.yml      # Local dev stack (Cassandra + warehouses)

config/
├── pipeline.example.yaml   # Example configuration
├── masking-rules.yaml      # PII/PHI field classifications
└── schema-mappings.yaml    # Cassandra → warehouse type mappings

scripts/
├── setup-local-env.sh      # Initialize local databases
├── seed-test-data.sh       # Insert test data into Cassandra
└── run-integration-tests.sh # Run full test suite with Docker

.env.example                # Example environment variables
requirements.txt            # Production dependencies
requirements-dev.txt        # Development dependencies
pyproject.toml              # Project metadata, mypy/black config
pytest.ini                  # Pytest configuration
.pre-commit-config.yaml     # Pre-commit hooks (black, mypy, ruff)
README.md                   # Project overview (points to quickstart.md)
```

**Structure Decision**: Single pipeline application structure selected. This is a focused data engineering service, not a web app or mobile app. The structure separates concerns cleanly:
- `src/cdc/`: Cassandra-specific CDC reading logic
- `src/transform/`: Source-agnostic transformation (masking, mapping)
- `src/sinks/`: Destination-specific writers with pluggable interface
- `src/observability/`: Cross-cutting concerns (metrics, logs, traces)
- `src/config/`: Configuration management
- `tests/`: Comprehensive test suite mirroring src/ structure with additional chaos/performance tests

## Complexity Tracking

No constitutional violations detected. All complexity is justified by functional requirements:
- Multi-destination support (3 warehouses) is explicit requirement, not over-engineering
- Masking/observability/retry logic are all mandated by spec
- Pluggable sink architecture adds minimal abstraction justified by 3 destinations
- No unnecessary frameworks or premature optimization

**Status**: CLEAN - No violations to justify
