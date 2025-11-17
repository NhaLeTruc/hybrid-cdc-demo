# Tasks: Secure Multi-Destination CDC Pipeline

**Input**: Design documents from `/specs/001-secure-cdc-pipeline/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: TDD is NON-NEGOTIABLE per project constitution Principle V. All test tasks MUST be completed before implementation tasks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4, US5)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Paths follow plan.md structure decision: Single pipeline application

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create project directory structure (src/, tests/, docker/, config/, scripts/, data/)
- [x] T002 Initialize Python project with pyproject.toml (Python 3.11+, project metadata, tool configs)
- [x] T003 [P] Create requirements.txt with production dependencies
- [x] T004 [P] Create requirements-dev.txt with development dependencies
- [x] T005 [P] Configure pytest in pytest.ini (asyncio mode, coverage settings)
- [x] T006 [P] Configure pre-commit hooks in .pre-commit-config.yaml (black, mypy, ruff)
- [x] T007 [P] Create .env.example template file for environment variables
- [x] T008 [P] Create .gitignore for Python project (venv, __pycache__, .env, data/)
- [x] T009 [P] Create README.md with project overview (link to quickstart.md)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T010 Create docker/docker-compose.yml with Cassandra 4.1 service (port 9042, CDC enabled)
- [x] T011 Add Postgres 15 service to docker-compose.yml (port 5432)
- [x] T012 Add ClickHouse 23 service to docker-compose.yml (ports 8123, 9000)
- [x] T013 Add TimescaleDB 2.13 service to docker-compose.yml (port 5433)
- [x] T014 [P] Create docker/Dockerfile for production pipeline image (multi-stage build)
- [x] T015 [P] Create docker/Dockerfile.dev with test dependencies
- [x] T016 Create config/pipeline.example.yaml based on contracts/config-schema.yaml
- [x] T017 [P] Create config/masking-rules.yaml with PII/PHI field definitions
- [x] T018 [P] Create config/schema-mappings.yaml for Cassandra → warehouse type mappings
- [x] T019 Create src/config/__init__.py (empty)
- [x] T020 Create src/config/settings.py with Pydantic Settings models per config-schema.yaml
- [x] T021 Create src/config/loader.py to load YAML configuration files
- [x] T022 Create src/models/__init__.py (empty)
- [x] T023 [P] Create src/models/event.py with ChangeEvent dataclass per data-model.md
- [x] T024 [P] Create src/models/offset.py with ReplicationOffset dataclass per data-model.md
- [x] T025 [P] Create src/models/schema.py with SchemaVersion dataclass per data-model.md
- [x] T026 Create src/observability/__init__.py (empty)
- [x] T027 Create src/observability/logging.py with structlog JSON configuration
- [x] T028 Create src/observability/metrics.py with Prometheus metrics setup per metrics-api.yaml
- [x] T029 Create src/observability/tracing.py with OpenTelemetry configuration (optional)
- [x] T030 Create tests/conftest.py with pytest fixtures for testcontainers (Cassandra, Postgres, ClickHouse, TimescaleDB)
- [x] T031 Create scripts/wait-for-databases.sh to check database health
- [x] T032 Create scripts/setup-local-env.sh to initialize schemas and seed test data

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Data Replication with Exactly-Once Delivery (Priority: P1) 🎯 MVP

**Goal**: Replicate data changes from Cassandra to all three warehouses with exactly-once delivery guarantees

**Independent Test**: Deploy pipeline, make changes in Cassandra (INSERT, UPDATE, DELETE), verify all three destinations receive exactly the same changes with no duplicates or missing records. Kill and restart pipeline mid-replication to verify resume from correct offset.

### Tests for User Story 1 (TDD - Write FIRST, ensure FAIL before implementation) ⚠️

- [x] T033 [P] [US1] Create tests/unit/test_event_parsing.py for CDC event parsing logic
- [x] T034 [P] [US1] Create tests/unit/test_offset_management.py for offset read/write/commit logic
- [x] T035 [P] [US1] Create tests/contract/test_event_schema.py validating ChangeEvent against event-schema.json
- [x] T036 [P] [US1] Create tests/contract/test_offset_schema.py validating ReplicationOffset against offset-schema.json
- [x] T037 [P] [US1] Create tests/integration/test_cassandra_to_postgres.py for end-to-end Cassandra → Postgres replication
- [x] T038 [P] [US1] Create tests/integration/test_cassandra_to_clickhouse.py for end-to-end Cassandra → ClickHouse replication
- [x] T039 [P] [US1] Create tests/integration/test_cassandra_to_timescaledb.py for end-to-end Cassandra → TimescaleDB replication
- [x] T040 [US1] Create tests/integration/test_exactly_once.py verifying no duplicates after pipeline restart
- [x] T041 [US1] Create tests/integration/test_crash_recovery.py simulating crash mid-batch and verifying offset recovery

### Implementation for User Story 1

- [x] T042 Create src/cdc/__init__.py (empty)
- [x] T043 [US1] Implement src/cdc/reader.py with Cassandra CDC commitlog reader (read commitlog files from cdc_raw directory)
- [x] T044 [US1] Implement src/cdc/parser.py to parse binary commitlog format into ChangeEvent objects
- [x] T045 [US1] Implement src/cdc/offset.py with offset management (read last offset, update offset, atomic commit)
- [x] T046 Create src/sinks/__init__.py (empty)
- [x] T047 [US1] Create src/sinks/base.py with abstract BaseSink interface (connect, write_batch, commit_offset, health_check methods)
- [x] T048 [P] [US1] Implement src/sinks/postgres.py with PostgresSink (psycopg async, INSERT ON CONFLICT, transactional offset commit)
- [x] T049 [P] [US1] Implement src/sinks/clickhouse.py with ClickHouseSink (clickhouse-driver, ReplacingMergeTree, separate offset table)
- [x] T050 [P] [US1] Implement src/sinks/timescaledb.py with TimescaleDBSink (inherit from PostgresSink, TimescaleDB hypertable support)
- [x] T051 [US1] Create src/main.py with pipeline entrypoint (parse config, initialize sinks, start CDC reader loop)
- [x] T052 [US1] Implement async event batching logic in src/main.py (micro-batching with configurable batch_size)
- [x] T053 [US1] Implement parallel sink writes in src/main.py (asyncio concurrent writes to all 3 warehouses)
- [x] T054 [US1] Implement backpressure handling in src/main.py (semaphores limiting in-flight batches per sink)
- [x] T055 [US1] Add offset commit logic after successful batch writes in src/main.py
- [x] T056 [US1] Create database migration scripts in scripts/create-offset-table.sql for Postgres _cdc_offsets table
- [x] T057 [US1] Update scripts/setup-local-env.sh to create destination tables in Postgres, ClickHouse, TimescaleDB
- [x] T058 [US1] Run all User Story 1 tests and verify they pass

**Checkpoint**: User Story 1 complete and independently testable. Pipeline replicates data with exactly-once delivery.

---

## Phase 4: User Story 2 - Sensitive Data Protection (Priority: P2)

**Goal**: Automatically mask PII/PHI fields during replication for GDPR/HIPAA compliance

**Independent Test**: Configure PII/PHI field classifications, insert test records with sensitive data into Cassandra, verify replicated records in all warehouses show masked values (hashed or tokenized) while non-sensitive fields remain readable.

### Tests for User Story 2 (TDD - Write FIRST, ensure FAIL before implementation) ⚠️

- [x] T059 [P] [US2] Create tests/unit/test_masking.py for SHA-256 hashing and HMAC tokenization functions
- [x] T060 [P] [US2] Create tests/unit/test_schema_mapper.py for Cassandra → warehouse type mapping logic
- [x] T061 [P] [US2] Create tests/contract/test_type_conversions.py validating type mappings preserve semantics
- [x] T062 [US2] Create tests/integration/test_pii_masking.py verifying PII fields (email, phone, SSN) are hashed in warehouses
- [x] T063 [US2] Create tests/integration/test_phi_masking.py verifying PHI fields (medical_record_number) are tokenized
- [x] T064 [US2] Create tests/integration/test_masking_configuration.py verifying masking-rules.yaml is correctly applied

### Implementation for User Story 2

- [x] T065 Create src/transform/__init__.py (empty)
- [x] T066 [US2] Implement src/transform/masking.py with SHA-256 hashing function for PII fields
- [x] T067 [US2] Implement HMAC tokenization function in src/transform/masking.py for PHI fields
- [x] T068 [US2] Implement masking rule loader in src/transform/masking.py (read masking-rules.yaml, classify fields)
- [x] T069 [US2] Create src/transform/schema_mapper.py to load schema-mappings.yaml and map Cassandra types to warehouse types
- [x] T070 [US2] Implement type conversion functions in src/transform/schema_mapper.py (UUID, TIMESTAMP, MAP→JSON, SET→ARRAY)
- [x] T071 [US2] Create src/transform/validator.py to validate event schema against SchemaVersion
- [x] T072 [US2] Create src/models/masked_field.py with MaskedField dataclass per data-model.md
- [x] T073 [US2] Integrate masking logic into src/main.py pipeline (apply masking before sink writes)
- [x] T074 [US2] Add audit logging for masked fields in src/observability/logging.py (log field_name, classification, masking_strategy)
- [x] T075 [US2] Update sink implementations to write masked values (src/sinks/postgres.py, clickhouse.py, timescaledb.py)
- [x] T076 [US2] Run all User Story 2 tests and verify they pass

**Checkpoint**: User Stories 1 AND 2 both work independently. PII/PHI fields are masked in warehouses.

---

## Phase 5: User Story 3 - Real-Time Operational Visibility (Priority: P3)

**Goal**: Expose real-time metrics showing replication lag, throughput, error rates, and backlog depth for each destination

**Independent Test**: Start replication with metrics endpoint enabled, generate load in Cassandra, query metrics API to verify real-time lag (seconds behind source), throughput (events/sec), error counts, and per-destination health status.

### Tests for User Story 3 (TDD - Write FIRST, ensure FAIL before implementation) ⚠️

- [x] T077 [P] [US3] Create tests/unit/test_metrics.py for Prometheus metric collection logic
- [x] T078 [P] [US3] Create tests/contract/test_metrics_api.py validating /metrics endpoint matches metrics-api.yaml spec
- [x] T079 [P] [US3] Create tests/contract/test_health_api.py validating /health endpoint matches metrics-api.yaml spec
- [x] T080 [US3] Create tests/integration/test_metrics_collection.py verifying metrics update during replication
- [x] T081 [US3] Create tests/integration/test_health_checks.py verifying dependency health detection

### Implementation for User Story 3

- [x] T082 [US3] Implement Prometheus metrics in src/observability/metrics.py (cdc_events_processed_total counter)
- [x] T083 [US3] Add cdc_replication_lag_seconds gauge to src/observability/metrics.py
- [x] T084 [US3] Add cdc_events_per_second gauge to src/observability/metrics.py
- [x] T085 [US3] Add cdc_errors_total counter to src/observability/metrics.py
- [x] T086 [US3] Add cdc_backlog_depth gauge to src/observability/metrics.py
- [x] T087 [US3] Create HTTP server for /metrics endpoint in src/observability/metrics.py (prometheus-client HTTP server)
- [x] T088 [US3] Create src/observability/health.py with health check endpoint implementation
- [x] T089 [US3] Implement dependency health checks in src/observability/health.py (Cassandra, Postgres, ClickHouse, TimescaleDB)
- [x] T090 [US3] Create src/models/destination_sink.py with DestinationSink dataclass per data-model.md
- [x] T091 [US3] Integrate metrics collection into src/main.py (increment counters, update gauges during replication)
- [x] T092 [US3] Integrate health checks into src/main.py (periodic health check loop, update DestinationSink status)
- [x] T093 [US3] Add lag calculation logic in src/cdc/offset.py (compare Cassandra timestamp to current time)
- [x] T094 [US3] Add throughput tracking in src/sinks/base.py (moving average of events per second)
- [x] T095 [US3] Run all User Story 3 tests and verify they pass

**Checkpoint**: All three user stories independently functional. Metrics and health endpoints expose real-time observability.

---

## Phase 6: User Story 4 - Automatic Failure Recovery (Priority: P4)

**Goal**: Automatically recover from transient failures (network partitions, database downtime) without data loss or manual intervention

**Independent Test**: Simulate network partition (firewall rule blocks destination), verify pipeline retries with exponential backoff, remove network block, confirm automatic reconnection and resumption without data loss.

### Tests for User Story 4 (TDD - Write FIRST, ensure FAIL before implementation) ⚠️

- [x] T096 [P] [US4] Create tests/unit/test_retry_logic.py for exponential backoff calculation and jitter
- [x] T097 [P] [US4] Create tests/unit/test_dlq.py for dead letter queue write logic
- [x] T098 [US4] Create tests/chaos/test_network_partition.py using Toxiproxy to simulate network failures
- [x] T099 [US4] Create tests/chaos/test_slow_destination.py simulating high latency destinations
- [ ] T100 [US4] Create tests/chaos/test_database_restart.py simulating database shutdown and restart

### Implementation for User Story 4

- [ ] T101 [US4] Create src/sinks/retry.py with RetryPolicy dataclass and retry logic (exponential backoff with jitter)
- [ ] T102 [US4] Implement retry wrapper function in src/sinks/retry.py (max_attempts, backoff_multiplier, jitter)
- [ ] T103 [US4] Create src/dlq/__init__.py (empty)
- [ ] T104 [US4] Implement src/dlq/writer.py with DLQ JSONL file writer
- [ ] T105 [US4] Create src/models/dead_letter_event.py with DeadLetterEvent dataclass per data-model.md
- [ ] T106 [US4] Integrate retry logic into all sink implementations (src/sinks/postgres.py, clickhouse.py, timescaledb.py)
- [ ] T107 [US4] Add DLQ routing for failed events after max retries in src/main.py
- [ ] T108 [US4] Implement connection recovery logic in src/sinks/base.py (reconnect on connection errors)
- [ ] T109 [US4] Add transient vs permanent error classification in src/sinks/base.py
- [ ] T110 [US4] Create data/dlq/ directory and .gitkeep file
- [ ] T111 [US4] Update metrics to track retry attempts (cdc_retry_attempts_total counter)
- [ ] T112 [US4] Run all User Story 4 tests and verify they pass

**Checkpoint**: All four user stories independently functional. Pipeline recovers automatically from transient failures.

---

## Phase 7: User Story 5 - Schema Evolution Handling (Priority: P5)

**Goal**: Gracefully handle Cassandra schema changes (ADD COLUMN, DROP COLUMN, ALTER TYPE) without crashing or requiring manual reconfiguration

**Independent Test**: Start replication, add new column to Cassandra table via ALTER TABLE, insert records with new column, verify pipeline detects schema change and either propagates new column to destinations or logs warning and continues.

### Tests for User Story 5 (TDD - Write FIRST, ensure FAIL before implementation) ⚠️

- [ ] T113 [P] [US5] Create tests/unit/test_schema_detection.py for schema change detection logic
- [ ] T114 [US5] Create tests/integration/test_add_column.py verifying ADD COLUMN handling
- [ ] T115 [US5] Create tests/integration/test_drop_column.py verifying DROP COLUMN handling
- [ ] T116 [US5] Create tests/integration/test_alter_type.py verifying ALTER TYPE handling
- [ ] T117 [US5] Create tests/integration/test_schema_incompatibility.py verifying unsupported types route to DLQ

### Implementation for User Story 5

- [ ] T118 [US5] Implement schema detection in src/cdc/reader.py (query system_schema.tables on startup and periodically)
- [ ] T119 [US5] Implement schema comparison logic in src/models/schema.py (detect ADD/DROP/ALTER changes)
- [ ] T120 [US5] Create SchemaChange dataclass in src/models/schema.py per data-model.md
- [ ] T121 [US5] Implement schema version tracking in src/cdc/reader.py (store SchemaVersion, increment version on change)
- [ ] T122 [US5] Add schema validation in src/transform/validator.py (validate ChangeEvent against current SchemaVersion)
- [ ] T123 [US5] Implement column mapping updates in src/transform/schema_mapper.py (handle new/dropped columns)
- [ ] T124 [US5] Add schema incompatibility detection in src/transform/schema_mapper.py (e.g., Cassandra MAP unsupported)
- [ ] T125 [US5] Route schema-incompatible events to DLQ in src/main.py with clear error messages
- [ ] T126 [US5] Add schema change logging in src/observability/logging.py (log detected changes)
- [ ] T127 [US5] Run all User Story 5 tests and verify they pass

**Checkpoint**: All five user stories independently functional. Pipeline handles schema evolution gracefully.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T128 [P] Create comprehensive type hints across all modules and run mypy validation
- [ ] T129 [P] Add docstrings to all public functions and classes (Google/NumPy style)
- [ ] T130 [P] Run black formatter on entire codebase
- [ ] T131 [P] Run ruff linter and fix all issues
- [ ] T132 Create scripts/seed-test-data.sh to insert 1000 users and 5000 orders into Cassandra
- [ ] T133 Create scripts/run-integration-tests.sh to orchestrate Docker Compose and pytest
- [ ] T134 [P] Create performance benchmark in tests/performance/benchmark_throughput.py (measure events/sec, p99 latency)
- [ ] T135 Run performance benchmark and document results in quickstart.md
- [ ] T136 [P] Add error handling and graceful shutdown (SIGTERM, SIGINT) in src/main.py
- [ ] T137 Validate quickstart.md by following all steps and fixing any issues
- [ ] T138 Run full test suite with coverage report (pytest --cov=src --cov-report=html)
- [ ] T139 Verify 80%+ code coverage per constitution requirement
- [ ] T140 Create example Grafana dashboard JSON for visualizing Prometheus metrics (optional)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User Story 1 (P1): Can start after Foundational - No dependencies on other stories
  - User Story 2 (P2): Can start after Foundational - May integrate with US1 but independently testable
  - User Story 3 (P3): Can start after Foundational - May integrate with US1 but independently testable
  - User Story 4 (P4): Can start after Foundational - Builds on US1 retry needs but independently testable
  - User Story 5 (P5): Can start after Foundational - Enhances US1 but independently testable
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - **No dependencies on other stories**
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Integrates with US1 pipeline but **independently testable**
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Observes US1 replication but **independently testable**
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - Enhances US1 resilience but **independently testable**
- **User Story 5 (P5)**: Can start after Foundational (Phase 2) - Extends US1 schema handling but **independently testable**

### Within Each User Story

- **Tests MUST be written and FAIL before implementation** (TDD non-negotiable)
- Models before services
- Services before sinks
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- **Setup tasks (Phase 1)**: All tasks marked [P] can run in parallel
- **Foundational tasks (Phase 2)**: Tasks T014-T015 (Dockerfiles) can run parallel, T016-T018 (configs) can run parallel, T023-T025 (models) can run parallel
- **Once Foundational completes**: All user stories (US1-US5) can start in parallel if team capacity allows
- **Within User Story 1**: Tests T033-T039 can run parallel, sinks T048-T050 can run parallel
- **Within User Story 2**: Tests T059-T061 can run parallel
- **Within User Story 3**: Tests T077-T079 can run parallel
- **Within User Story 4**: Tests T096-T097 can run parallel
- **Within User Story 5**: Test T113 can run independently
- **Polish tasks (Phase 8)**: Tasks T128-T131 (formatting, linting, docs) can run parallel

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task T033: Create tests/unit/test_event_parsing.py
Task T034: Create tests/unit/test_offset_management.py
Task T035: Create tests/contract/test_event_schema.py
Task T036: Create tests/contract/test_offset_schema.py
Task T037: Create tests/integration/test_cassandra_to_postgres.py
Task T038: Create tests/integration/test_cassandra_to_clickhouse.py
Task T039: Create tests/integration/test_cassandra_to_timescaledb.py

# Then launch all sink implementations together:
Task T048: Implement src/sinks/postgres.py
Task T049: Implement src/sinks/clickhouse.py
Task T050: Implement src/sinks/timescaledb.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Data Replication with Exactly-Once Delivery)
4. **STOP and VALIDATE**: Test User Story 1 independently using quickstart.md
5. Deploy/demo if ready

**MVP Scope**: Tasks T001-T058 (58 tasks)

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Add User Story 4 → Test independently → Deploy/Demo
6. Add User Story 5 → Test independently → Deploy/Demo
7. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001-T032)
2. Once Foundational is done:
   - Developer A: User Story 1 (T033-T058)
   - Developer B: User Story 2 (T059-T076)
   - Developer C: User Story 3 (T077-T095)
3. Stories complete and integrate independently

---

## Notes

- **[P] tasks** = different files, no dependencies
- **[Story] label** maps task to specific user story for traceability
- **Each user story should be independently completable and testable**
- **Verify tests fail before implementing** (TDD red-green-refactor)
- **Commit after each task or logical group**
- **Stop at any checkpoint to validate story independently**
- **Total tasks**: 140 (Setup: 9, Foundational: 23, US1: 26, US2: 18, US3: 19, US4: 17, US5: 15, Polish: 13)
- **Parallel opportunities**: 45 tasks marked [P] can run concurrently
- **MVP scope**: 58 tasks (Setup + Foundational + User Story 1)
- **Constitution compliance**: TDD enforced (tests before implementation), 80%+ coverage verified in T139

---

## Task Summary

| Phase | User Story | Tasks | Parallel Tasks | Description |
|-------|-----------|-------|----------------|-------------|
| 1 | Setup | T001-T009 (9) | 6 | Project initialization |
| 2 | Foundational | T010-T032 (23) | 10 | Blocking infrastructure |
| 3 | US1 (P1) | T033-T058 (26) | 11 | Data replication with exactly-once delivery 🎯 MVP |
| 4 | US2 (P2) | T059-T076 (18) | 4 | PII/PHI masking for compliance |
| 5 | US3 (P3) | T077-T095 (19) | 5 | Real-time metrics and observability |
| 6 | US4 (P4) | T096-T112 (17) | 3 | Automatic failure recovery |
| 7 | US5 (P5) | T113-T127 (15) | 1 | Schema evolution handling |
| 8 | Polish | T128-T140 (13) | 5 | Cross-cutting improvements |
| **Total** | | **140 tasks** | **45 parallel** | |

---

## Independent Test Criteria

### User Story 1 (P1)
Deploy pipeline, make changes in Cassandra (INSERT, UPDATE, DELETE), verify all three destinations receive exactly the same changes with no duplicates or missing records. Kill and restart pipeline mid-replication to verify resume from correct offset.

### User Story 2 (P2)
Configure PII/PHI field classifications (email, SSN, phone, medical_record_number), insert test records with sensitive data into Cassandra, verify replicated records in all warehouses show masked values (hashed or tokenized) while non-sensitive fields remain readable.

### User Story 3 (P3)
Start replication with metrics endpoint enabled, generate load in Cassandra, query metrics API or dashboard to verify real-time lag (seconds behind source), throughput (events/sec), error counts, and per-destination health status.

### User Story 4 (P4)
Simulate network partition (firewall rule blocks destination), verify pipeline retries with exponential backoff, remove network block, confirm automatic reconnection and resumption without data loss. Repeat for destination database restart scenario.

### User Story 5 (P5)
Start replication, add new column to Cassandra table via ALTER TABLE, insert records with new column, verify pipeline detects schema change and either propagates new column to destinations (if auto-migration enabled) or logs warning and continues replicating existing columns.
