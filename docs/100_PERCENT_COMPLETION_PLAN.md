# Implementation Plan: Achieve 100% Project Completion

**Created**: 2025-11-20
**Current Status**: 45% coverage, 199/199 tests passing
**Target**: 100% feature-complete, production-ready CDC pipeline
**Estimated Timeline**: 3-4 weeks

---

## Executive Summary

This plan outlines the path from current state (infrastructure validated, tests passing) to 100% project completion with a production-ready, fully-featured CDC pipeline. The plan is organized into 4 major phases with clear milestones and acceptance criteria.

**Current State**:
- ✅ All 199 tests passing (100% pass rate)
- ✅ Test infrastructure complete and validated
- ✅ Core models and configuration in place
- ⚠️ 45% code coverage (target: 80%+)
- ⚠️ Many test assertions commented out (waiting for pipeline implementation)
- ⚠️ Core pipeline orchestrator at 0% coverage

**Target State**:
- ✅ 80%+ code coverage across all modules
- ✅ All test assertions uncommented and passing
- ✅ Full end-to-end CDC pipeline operational
- ✅ All 5 user stories fully implemented
- ✅ Production-ready with documentation
- ✅ Performance benchmarks met

---

## Phase 1: Coverage Foundation (Week 1) - Priority: Critical

**Goal**: Increase coverage from 45% to 65% by testing core untested modules

**Rationale**: Many critical modules have 0% coverage. Without tests, we can't safely implement features or refactor. This phase establishes a safety net for all future work.

### 1.1 Test Core Pipeline Orchestrator (Days 1-2)

**Target Module**: `src/main.py` (121 lines, 0% coverage)

**Why First**: This is the heart of the application. Every other feature depends on it working correctly.

**Tasks**:
- [ ] **T1.1.1**: Create `tests/integration/test_pipeline_startup.py`
  - Test `CDCPipeline.__init__()` with valid configuration
  - Test configuration loading from YAML file
  - Test configuration validation errors
  - Test dependency initialization (reader, sinks, metrics)

- [ ] **T1.1.2**: Create `tests/integration/test_pipeline_lifecycle.py`
  - Test `pipeline.start()` and `pipeline.stop()` lifecycle
  - Test graceful shutdown with SIGTERM
  - Test pipeline state transitions
  - Test cleanup of resources on shutdown

- [ ] **T1.1.3**: Create `tests/integration/test_pipeline_e2e_simple.py`
  - Test reading 1 event from Cassandra commitlog
  - Test parsing event into ChangeEvent
  - Test writing event to all 3 destinations
  - Test offset commit after successful write
  - **Uncomment assertions** in existing integration tests

- [ ] **T1.1.4**: Create `tests/unit/test_pipeline_batch_processing.py`
  - Test batch size configuration
  - Test batch assembly logic
  - Test partial batch handling
  - Test empty batch handling

**Expected Coverage Increase**: +15% (0% → 90% for main.py)

**Success Criteria**:
- All new tests pass
- Can start/stop pipeline without errors
- Pipeline processes at least 1 event end-to-end
- Existing integration test assertions uncommented

### 1.2 Test Configuration Loading (Day 3)

**Target Module**: `src/config/loader.py` (60 lines, 0% coverage)

**Tasks**:
- [ ] **T1.2.1**: Create `tests/unit/test_config_loader.py`
  - Test `load_config()` with valid YAML
  - Test `load_masking_rules()` parsing
  - Test `load_schema_mappings()` parsing
  - Test file not found errors
  - Test invalid YAML syntax errors
  - Test schema validation errors

- [ ] **T1.2.2**: Create test fixtures for config files
  - Create `tests/fixtures/config/valid_pipeline.yaml`
  - Create `tests/fixtures/config/invalid_pipeline.yaml`
  - Create `tests/fixtures/config/valid_masking.yaml`
  - Create `tests/fixtures/config/valid_mappings.yaml`

**Expected Coverage Increase**: +4% (0% → 100% for loader.py)

**Success Criteria**:
- Configuration loading thoroughly tested
- All error paths covered
- Clear error messages for invalid configs

### 1.3 Test Observability Infrastructure (Day 4)

**Target Modules**:
- `src/observability/logging.py` (51 lines, 0% coverage)
- `src/observability/tracing.py` (29 lines, 0% coverage)

**Tasks**:
- [ ] **T1.3.1**: Create `tests/unit/test_logging.py`
  - Test logger initialization
  - Test JSON log format
  - Test log levels (DEBUG, INFO, WARNING, ERROR)
  - Test structured logging with context
  - Test log output to file and stdout

- [ ] **T1.3.2**: Create `tests/unit/test_tracing.py`
  - Test OpenTelemetry tracer initialization
  - Test span creation and completion
  - Test trace context propagation
  - Test tracing disabled mode (optional feature)

- [ ] **T1.3.3**: Add logging to existing tests
  - Verify logs are generated during pipeline operations
  - Test log correlation with metrics

**Expected Coverage Increase**: +5% (0% → 90% for both modules)

**Success Criteria**:
- All logging paths tested
- JSON logs validated
- Tracing setup tested (even if optional)

### 1.4 Test Validation Infrastructure (Day 5)

**Target Module**: `src/transform/validator.py` (73 lines, 0% coverage)

**Tasks**:
- [ ] **T1.4.1**: Create `tests/unit/test_validator.py`
  - Test schema validation for ChangeEvent
  - Test schema validation for ReplicationOffset
  - Test validation error messages
  - Test valid vs invalid events
  - Test type coercion and conversion

- [ ] **T1.4.2**: Create `tests/integration/test_validation_pipeline.py`
  - Test invalid events route to DLQ
  - Test validation errors are logged
  - Test metrics track validation failures

**Expected Coverage Increase**: +4% (0% → 100% for validator.py)

**Success Criteria**:
- All validation rules tested
- Invalid events properly rejected
- Clear error messages for users

### Phase 1 Milestone

**Coverage Target**: 65% (from 45%)
**Timeline**: Week 1 (5 days)
**Deliverables**:
- Core pipeline orchestrator tested and working
- Configuration loading tested
- Observability infrastructure tested
- Validation framework tested
- ~50 new tests added

**Acceptance Criteria**:
- Coverage reaches 65%+
- All 250+ tests passing
- Pipeline can process events end-to-end
- No test assertions commented out in core flows

---

## Phase 2: Sink Implementation Coverage (Week 2) - Priority: High

**Goal**: Increase coverage from 65% to 75% by testing sink implementations

**Rationale**: Sinks are the critical write path. Low coverage (18-21%) means we can't confidently deploy to production. This phase ensures reliable data delivery to all destinations.

### 2.1 Test Postgres Sink (Days 6-7)

**Target Module**: `src/sinks/postgres.py` (82 lines, 18% coverage)

**Tasks**:
- [ ] **T2.1.1**: Create `tests/unit/test_postgres_sink.py`
  - Test connection establishment
  - Test `write_batch()` with single event
  - Test `write_batch()` with multiple events
  - Test INSERT ON CONFLICT (upsert) behavior
  - Test transaction management
  - Test rollback on error

- [ ] **T2.1.2**: Create `tests/integration/test_postgres_sink_e2e.py`
  - Test writing 1000 events successfully
  - Test exactly-once semantics (duplicate handling)
  - Test connection pool management
  - Test concurrent writes from multiple workers
  - Test offset commit after successful writes

- [ ] **T2.1.3**: Test error scenarios
  - Test connection failure and retry
  - Test timeout handling
  - Test constraint violations
  - Test deadlock detection and recovery

**Expected Coverage Increase**: +4% (18% → 90% for postgres.py)

### 2.2 Test ClickHouse Sink (Days 8-9)

**Target Module**: `src/sinks/clickhouse.py` (74 lines, 19% coverage)

**Tasks**:
- [ ] **T2.2.1**: Create `tests/unit/test_clickhouse_sink.py`
  - Test connection establishment
  - Test `write_batch()` with ReplacingMergeTree
  - Test data type conversions (Cassandra → ClickHouse)
  - Test batch assembly and buffer management

- [ ] **T2.2.2**: Create `tests/integration/test_clickhouse_sink_e2e.py`
  - Test writing 1000 events to ClickHouse
  - Test deduplication with ReplacingMergeTree
  - Test query performance after replication
  - Test separate offset table management

- [ ] **T2.2.3**: Test ClickHouse-specific features
  - Test compression settings
  - Test partitioning by date
  - Test TTL policies (if configured)

**Expected Coverage Increase**: +4% (19% → 90% for clickhouse.py)

### 2.3 Test TimescaleDB Sink (Day 10)

**Target Module**: `src/sinks/timescaledb.py` (63 lines, 21% coverage)

**Tasks**:
- [ ] **T2.3.1**: Create `tests/unit/test_timescaledb_sink.py`
  - Test connection establishment
  - Test hypertable creation
  - Test time-series optimizations
  - Test chunk management

- [ ] **T2.3.2**: Create `tests/integration/test_timescaledb_sink_e2e.py`
  - Test writing time-series data
  - Test hypertable automatic partitioning
  - Test compression policies
  - Test retention policies
  - **Uncomment assertions** in `test_cassandra_to_timescaledb.py`

**Expected Coverage Increase**: +3% (21% → 90% for timescaledb.py)

**Success Criteria**:
- All assertions uncommented in TimescaleDB tests
- Hypertable features validated

### Phase 2 Milestone

**Coverage Target**: 75% (from 65%)
**Timeline**: Week 2 (5 days)
**Deliverables**:
- All 3 sinks thoroughly tested
- End-to-end write paths validated
- All sink assertions uncommented
- ~40 new tests added

**Acceptance Criteria**:
- Coverage reaches 75%+
- All 290+ tests passing
- All 3 destinations receiving data reliably
- Exactly-once semantics validated for all sinks

---

## Phase 3: Feature Completion (Week 3) - Priority: High

**Goal**: Implement and test remaining user stories (US2-US5)

**Rationale**: Core replication works (US1), now add production features: security, observability, resilience, schema evolution.

### 3.1 User Story 2: PII/PHI Masking (Days 11-12)

**Current Coverage**: `src/transform/masking.py` (82 lines, 74% coverage)

**Tasks**:
- [ ] **T3.1.1**: Improve masking coverage to 90%+
  - Test all masking algorithms (SHA-256, HMAC, tokenization)
  - Test masking rule application
  - Test selective field masking
  - Test masking with null/missing values

- [ ] **T3.1.2**: Integrate masking into pipeline
  - Add masking step before sink writes
  - Test masking in end-to-end flow
  - Verify masked data in destinations
  - Test audit logging of masked fields

- [ ] **T3.1.3**: Create `tests/integration/test_masking_e2e.py`
  - Test email masking (PII)
  - Test SSN masking (PII)
  - Test medical record tokenization (PHI)
  - Test non-sensitive fields remain clear
  - Verify compliance with GDPR/HIPAA requirements

**Expected Coverage Increase**: +1% (74% → 90% for masking.py)

**User Story Acceptance Criteria**:
- ✅ PII fields masked with irreversible hashing
- ✅ PHI fields tokenized with vault reference
- ✅ Non-sensitive fields remain readable
- ✅ Masking rules configurable via YAML
- ✅ Audit logs show which fields were masked

### 3.2 User Story 3: Real-Time Observability (Days 13-14)

**Current Coverage**:
- `src/observability/metrics.py` (26 lines, 88% coverage) ✅
- `src/observability/health.py` (143 lines, 59% coverage) ⚠️

**Tasks**:
- [ ] **T3.2.1**: Improve health check coverage to 90%+
  - Test all health check endpoints
  - Test dependency health checks (Cassandra, Postgres, ClickHouse, TimescaleDB)
  - Test health status aggregation
  - Test health check caching

- [ ] **T3.2.2**: Add metrics to pipeline flows
  - Add replication lag tracking
  - Add throughput metrics (events/sec per destination)
  - Add error rate metrics
  - Add backlog depth metrics

- [ ] **T3.2.3**: Create `tests/integration/test_metrics_e2e.py`
  - Test metrics update during replication
  - Test lag calculation accuracy
  - Test metrics export to Prometheus
  - Test dashboard queries
  - **Uncomment assertions** in existing metrics tests

**Expected Coverage Increase**: +3% (59% → 90% for health.py)

**User Story Acceptance Criteria**:
- ✅ Real-time lag metrics (<5s accuracy)
- ✅ Per-destination throughput visible
- ✅ Error rates tracked and alerted
- ✅ Backlog depth prevents overload
- ✅ p50/p95/p99 latency percentiles

### 3.3 User Story 4: Failure Recovery (Day 15)

**Current Coverage**:
- `src/sinks/retry.py` (71 lines, 73% coverage) ⚠️
- `src/dlq/writer.py` (36 lines, 69% coverage) ⚠️

**Tasks**:
- [ ] **T3.3.1**: Improve retry logic coverage to 90%+
  - Test exponential backoff calculation
  - Test jitter randomization
  - Test max retry attempts
  - Test retry policy per error type

- [ ] **T3.3.2**: Improve DLQ coverage to 90%+
  - Test writing events to DLQ
  - Test DLQ file format (JSONL)
  - Test DLQ rotation policies
  - Test DLQ replay mechanism

- [ ] **T3.3.3**: Enhance chaos tests
  - **Uncomment assertions** in `test_crash_recovery.py`
  - **Uncomment assertions** in `test_database_restart.py`
  - Test all network partition scenarios
  - Test all database failure scenarios
  - Validate automatic recovery in all cases

**Expected Coverage Increase**: +2% (73% → 90% for retry.py, 69% → 90% for dlq)

**User Story Acceptance Criteria**:
- ✅ Network partitions recovered automatically
- ✅ Database restarts handled gracefully
- ✅ Transient errors retried with backoff
- ✅ Permanent failures route to DLQ
- ✅ No data loss in any scenario

### 3.4 User Story 5: Schema Evolution (Day 15)

**Current Coverage**:
- `src/transform/schema_mapper.py` (102 lines, 47% coverage) ⚠️
- `src/models/schema.py` (117 lines, 76% coverage) ⚠️

**Tasks**:
- [ ] **T3.4.1**: Improve schema mapper coverage to 90%+
  - Test ADD COLUMN detection and propagation
  - Test DROP COLUMN handling
  - Test ALTER TYPE compatibility checks
  - Test RENAME COLUMN mapping

- [ ] **T3.4.2**: Improve schema model coverage to 90%+
  - Test schema version tracking
  - Test schema hash calculation
  - Test schema comparison logic
  - Test compatible vs incompatible changes

- [ ] **T3.4.3**: Enhance schema evolution tests
  - **Uncomment assertions** in `test_add_column.py`
  - **Uncomment assertions** in `test_drop_column.py`
  - **Uncomment assertions** in `test_alter_type.py`
  - **Uncomment assertions** in `test_schema_incompatibility.py`
  - Test all schema change scenarios

**Expected Coverage Increase**: +4% (47% → 90% for mapper, 76% → 90% for schema)

**User Story Acceptance Criteria**:
- ✅ ADD COLUMN propagated to destinations
- ✅ DROP COLUMN handled without errors
- ✅ Type changes validated for compatibility
- ✅ Incompatible changes route to DLQ
- ✅ Schema versions tracked

### Phase 3 Milestone

**Coverage Target**: 80% (from 75%)
**Timeline**: Week 3 (5 days)
**Deliverables**:
- All 5 user stories fully implemented
- All test assertions uncommented
- All features production-ready
- ~30 new tests added

**Acceptance Criteria**:
- Coverage reaches 80%+
- All 320+ tests passing
- All user story acceptance criteria met
- No commented assertions remain

---

## Phase 4: Production Readiness (Week 4) - Priority: Medium

**Goal**: Polish, performance tuning, documentation, deployment

**Rationale**: Features are complete, now ensure production quality: performance, documentation, operational runbooks.

### 4.1 Performance Optimization (Days 16-17)

**Tasks**:
- [ ] **T4.1.1**: Run performance benchmarks
  - Execute `tests/performance/benchmark_throughput.py`
  - Measure baseline: events/sec, latency p99
  - Target: 1000 events/sec, <5s p99 lag

- [ ] **T4.1.2**: Profile bottlenecks
  - Use `cProfile` to identify slow paths
  - Optimize hot paths (batch processing, serialization)
  - Tune connection pool sizes

- [ ] **T4.1.3**: Load testing
  - Test with 10K events/sec load
  - Test with 100K events/sec load
  - Measure resource usage (CPU, memory, disk)
  - Test backpressure mechanisms

**Deliverables**:
- Performance baseline documented
- Optimization recommendations
- Load test results

### 4.2 Documentation (Days 18-19)

**Tasks**:
- [ ] **T4.2.1**: API documentation
  - Document all public APIs with docstrings
  - Generate API docs with Sphinx
  - Add code examples for common use cases

- [ ] **T4.2.2**: Operational runbooks
  - Create `docs/OPERATIONS.md` with common tasks
  - Document monitoring and alerting setup
  - Document backup and recovery procedures
  - Create troubleshooting guide

- [ ] **T4.2.3**: Deployment documentation
  - Create `docs/DEPLOYMENT.md` for production
  - Document Kubernetes/Docker deployment
  - Document scaling strategies
  - Document security hardening

- [ ] **T4.2.4**: Update README and specs
  - Update README with production status
  - Update spec.md with implementation notes
  - Update quickstart.md with production tips

**Deliverables**:
- Complete API documentation
- Operational runbooks
- Deployment guides
- Updated project docs

### 4.3 Security Hardening (Day 20)

**Tasks**:
- [ ] **T4.3.1**: Security audit
  - Review TLS configuration
  - Audit secrets management
  - Check for SQL injection vulnerabilities
  - Validate PII/PHI masking implementation

- [ ] **T4.3.2**: Dependency security
  - Run `pip-audit` for vulnerable dependencies
  - Update all dependencies to latest secure versions
  - Pin all dependency versions

- [ ] **T4.3.3**: Security testing
  - Add tests for SQL injection prevention
  - Add tests for unauthorized access
  - Add tests for secrets exposure
  - Test TLS certificate validation

**Deliverables**:
- Security audit report
- All vulnerabilities patched
- Security tests added

### 4.4 CI/CD Pipeline (Day 20)

**Tasks**:
- [ ] **T4.4.1**: Set up GitHub Actions
  - Create `.github/workflows/test.yml`
  - Run tests on every PR
  - Block merge if tests fail or coverage drops

- [ ] **T4.4.2**: Set up Docker build pipeline
  - Create `.github/workflows/docker-build.yml`
  - Build and push Docker image on tag
  - Scan image for vulnerabilities

- [ ] **T4.4.3**: Set up release automation
  - Create `.github/workflows/release.yml`
  - Automate versioning and changelog
  - Publish releases to GitHub

**Deliverables**:
- CI/CD pipeline operational
- Automated testing on every PR
- Automated Docker builds

### Phase 4 Milestone

**Coverage Target**: 80%+ maintained
**Timeline**: Week 4 (5 days)
**Deliverables**:
- Performance benchmarks met
- Complete documentation
- Security audit passed
- CI/CD pipeline operational
- Production-ready release

**Acceptance Criteria**:
- Performance targets met (1K events/sec, <5s p99)
- All documentation complete
- Security vulnerabilities addressed
- CI/CD passing all checks
- Ready for production deployment

---

## Success Metrics

### Coverage Metrics
| Phase | Target Coverage | Actual Coverage | Status |
|-------|----------------|-----------------|--------|
| Start | - | 45% | ✅ Baseline |
| Phase 1 | 65% | TBD | 🚧 Pending |
| Phase 2 | 75% | TBD | 📋 Planned |
| Phase 3 | 80% | TBD | 📋 Planned |
| Phase 4 | 80%+ | TBD | 📋 Planned |

### Test Metrics
| Phase | Test Count | Pass Rate | Assertions Commented |
|-------|-----------|-----------|---------------------|
| Start | 199 | 100% | ~50 assertions |
| Phase 1 | ~250 | 100% | ~30 assertions |
| Phase 2 | ~290 | 100% | ~10 assertions |
| Phase 3 | ~320 | 100% | 0 assertions |
| Phase 4 | ~320 | 100% | 0 assertions |

### Feature Completion
| User Story | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|-----------|---------|---------|---------|---------|
| US1: Replication | 50% | 90% | 100% | 100% |
| US2: Masking | 30% | 50% | 100% | 100% |
| US3: Observability | 40% | 60% | 100% | 100% |
| US4: Recovery | 50% | 70% | 100% | 100% |
| US5: Schema Evolution | 40% | 60% | 100% | 100% |

---

## Risk Management

### High Risks
| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Uncommenting assertions reveals bugs | High | High | Incremental uncommenting, fix bugs immediately |
| Performance targets not met | Medium | High | Early benchmarking, iterative optimization |
| Coverage target too aggressive | Low | Medium | Focus on critical paths first, 70% acceptable |

### Medium Risks
| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Schema evolution edge cases | Medium | Medium | Comprehensive test coverage |
| Third-party API changes | Low | Medium | Pin all dependency versions |
| Timeline slippage | Medium | Low | Prioritize critical path, defer nice-to-haves |

### Low Risks
| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Documentation incomplete | Low | Low | Allocate dedicated time in Phase 4 |
| CI/CD setup issues | Low | Low | Use proven tools (GitHub Actions) |

---

## Contingency Plans

### If Coverage Target Not Met
**Trigger**: End of Phase 3, coverage < 75%
**Action**:
1. Identify highest-value untested modules
2. Focus on critical path only (skip nice-to-have features)
3. Accept 75% coverage if production-critical paths are tested

### If Timeline Slips
**Trigger**: Any phase overruns by >2 days
**Action**:
1. Re-prioritize tasks within current phase
2. Defer non-critical tasks to Phase 4
3. Extend Phase 4 or release as v1.0 with known limitations

### If Performance Targets Not Met
**Trigger**: Benchmarks show <500 events/sec or >10s lag
**Action**:
1. Profile and identify bottlenecks
2. Optimize hot paths
3. Consider architectural changes (e.g., message queue)
4. Document known performance limitations

---

## Definition of Done

### Phase Completion Criteria
- ✅ All planned tests written and passing
- ✅ Coverage target met for phase
- ✅ No new bugs introduced (all existing tests still pass)
- ✅ Code reviewed and approved
- ✅ Documentation updated

### Project Completion Criteria (100%)
- ✅ 80%+ code coverage across all modules
- ✅ 320+ tests passing (100% pass rate)
- ✅ Zero commented assertions
- ✅ All 5 user stories fully implemented and tested
- ✅ Performance benchmarks met (1K events/sec, <5s p99 lag)
- ✅ Security audit passed, no vulnerabilities
- ✅ Complete documentation (API, operations, deployment)
- ✅ CI/CD pipeline operational
- ✅ Production deployment successful
- ✅ All acceptance criteria met for all user stories

---

## Timeline Summary

| Week | Phase | Focus | Coverage Target | Deliverable |
|------|-------|-------|----------------|-------------|
| 1 | Phase 1 | Core untested modules | 65% | Pipeline working end-to-end |
| 2 | Phase 2 | Sink implementations | 75% | All destinations reliable |
| 3 | Phase 3 | Feature completion | 80% | All user stories done |
| 4 | Phase 4 | Production readiness | 80%+ | Production deployment |

**Total Duration**: 4 weeks (20 business days)
**Buffer**: Add 1 week for unexpected issues = **5 weeks total**

---

## Next Actions

### Immediate (This Week)
1. Review and approve this plan
2. Set up project tracking (GitHub Projects or Jira)
3. Create feature branches for each phase
4. Begin Phase 1, Task 1.1.1

### Week 1 Priorities
1. Get pipeline working end-to-end
2. Uncomment core integration test assertions
3. Reach 65% coverage
4. Validate basic replication works

### Success Indicators
- Daily: All tests still passing
- Weekly: Coverage increasing by 10%
- End of Month: 80%+ coverage, all features complete

---

## Appendix A: Test Organization

### New Test Files to Create

**Phase 1** (Week 1):
```
tests/integration/
  test_pipeline_startup.py           # T1.1.1
  test_pipeline_lifecycle.py         # T1.1.2
  test_pipeline_e2e_simple.py        # T1.1.3
tests/unit/
  test_pipeline_batch_processing.py  # T1.1.4
  test_config_loader.py              # T1.2.1
  test_logging.py                    # T1.3.1
  test_tracing.py                    # T1.3.2
  test_validator.py                  # T1.4.1
tests/integration/
  test_validation_pipeline.py        # T1.4.2
tests/fixtures/
  config/
    valid_pipeline.yaml
    invalid_pipeline.yaml
    valid_masking.yaml
    valid_mappings.yaml
```

**Phase 2** (Week 2):
```
tests/unit/
  test_postgres_sink.py              # T2.1.1
  test_clickhouse_sink.py            # T2.2.1
  test_timescaledb_sink.py           # T2.3.1
tests/integration/
  test_postgres_sink_e2e.py          # T2.1.2
  test_clickhouse_sink_e2e.py        # T2.2.2
  test_timescaledb_sink_e2e.py       # T2.3.2
```

**Phase 3** (Week 3):
```
tests/integration/
  test_masking_e2e.py                # T3.1.3
  test_metrics_e2e.py                # T3.2.3
```

**Phase 4** (Week 4):
```
docs/
  OPERATIONS.md                      # T4.2.2
  DEPLOYMENT.md                      # T4.2.3
  SECURITY_AUDIT.md                  # T4.3.1
.github/workflows/
  test.yml                           # T4.4.1
  docker-build.yml                   # T4.4.2
  release.yml                        # T4.4.3
```

---

## Appendix B: Resource Requirements

### Development Resources
- **Developer Time**: 1 FTE × 4 weeks = 160 hours
- **Review Time**: 20 hours (peer review of critical changes)
- **Testing Time**: Automated (CI/CD)

### Infrastructure Resources
- **Development**: Docker Desktop (8GB RAM, 10GB disk)
- **CI/CD**: GitHub Actions (free tier sufficient)
- **Staging**: Optional cloud environment for load testing
- **Production**: K8s cluster or Docker Swarm (to be determined in Phase 4)

### Tools & Services
- **Code Quality**: SonarCloud or CodeClimate (optional)
- **Security Scanning**: Snyk or Dependabot (free tier)
- **Documentation**: Sphinx + Read the Docs (free for open source)
- **Monitoring**: Prometheus + Grafana (self-hosted)

---

**Plan Created**: 2025-11-20
**Last Updated**: 2025-11-20
**Status**: Ready for Execution
**Next Review**: End of Phase 1 (Week 1)
