# Secure Multi-Destination CDC Pipeline

Production-grade change data capture (CDC) pipeline replicating data from Apache Cassandra to three data warehouse destinations: **Postgres**, **ClickHouse**, and **TimescaleDB** with exactly-once delivery semantics, PII/PHI masking, and comprehensive observability.

## Features

- 🔄 **Multi-Destination Replication**: Cassandra → Postgres + ClickHouse + TimescaleDB
- 🔒 **Security-First**: PII/PHI masking (SHA-256, HMAC), TLS 1.3+, secrets management
- ✅ **Exactly-Once Semantics**: Transactional offset commits, idempotent sinks
- 📊 **Full Observability**: Prometheus metrics, JSON logs, OpenTelemetry tracing
- 🔧 **Resilient**: Exponential backoff retry, dead letter queue, chaos-tested
- 📈 **Schema Evolution**: Graceful handling of ADD/DROP/ALTER COLUMN changes

## Quick Start

**Prerequisites**: Docker Desktop, Python 3.11+, 8GB RAM

```bash
# Clone repository
git clone https://github.com/NhaLeTruc/hybrid-cdc-demo.git
cd hybrid-cdc-demo

# Start databases (Cassandra, Postgres, ClickHouse, TimescaleDB)
docker-compose up -d

# Install dependencies
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Initialize schemas and seed test data
./scripts/setup-local-env.sh

# Configure pipeline
cp config/pipeline.example.yaml config/pipeline.yaml
cp .env.example .env

# Run CDC pipeline
python -m src.main
```

**Full quickstart guide**: See [specs/001-secure-cdc-pipeline/quickstart.md](specs/001-secure-cdc-pipeline/quickstart.md) for detailed 10-minute setup.

## Architecture

```
┌─────────────┐
│  Cassandra  │ (source)
│  CDC enabled│
└──────┬──────┘
       │ commitlog
       ↓
┌─────────────────────┐
│  CDC Pipeline       │
│  - Reader           │
│  - Masking (PII/PHI)│
│  - Multi-sink writer│
│  - Offset manager   │
└───┬────┬────┬───────┘
    │    │    │
    ↓    ↓    ↓
┌────────────────────┐
│ Postgres           │
│ ClickHouse         │
│ TimescaleDB        │
└────────────────────┘

Observability:
  /metrics (Prometheus)
  /health (JSON)
  logs/ (JSON)
```

## Project Structure

```
├── src/                  # Source code
│   ├── cdc/             # CDC commitlog reader
│   ├── transform/       # PII/PHI masking, schema mapping
│   ├── sinks/           # Postgres, ClickHouse, TimescaleDB writers
│   ├── observability/   # Metrics, logging, tracing
│   ├── config/          # Configuration management
│   ├── models/          # Data models
│   └── main.py          # Pipeline entrypoint
├── tests/               # Comprehensive test suite
│   ├── unit/           # Fast isolated tests
│   ├── integration/    # Docker-based E2E tests
│   ├── contract/       # Schema validation tests
│   ├── chaos/          # Network failure tests
│   └── performance/    # Benchmarks
├── docker/              # Dockerfiles and compose
├── config/              # YAML configurations
├── scripts/             # Setup and utility scripts
└── specs/               # Design documents

```

## Development

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests
pytest tests/unit/           # Fast unit tests
pytest tests/integration/    # Integration tests (requires Docker)
pytest --cov=src            # With coverage report

# Code quality
black src tests              # Format code
mypy src                     # Type checking
ruff check src tests         # Linting
```

## Testing

- **Unit Tests**: 80%+ coverage, fast (<1s), no external dependencies
- **Integration Tests**: Testcontainers (real Cassandra, Postgres, ClickHouse, TimescaleDB)
- **Contract Tests**: JSON schema validation (ChangeEvent, ReplicationOffset)
- **Chaos Tests**: Toxiproxy network failures (partitions, slow destinations)
- **Performance Tests**: Baseline 1K events/sec, <5s p99 lag

## Configuration

- **Pipeline**: `config/pipeline.yaml` (batch size, parallelism, retry policy)
- **Masking Rules**: `config/masking-rules.yaml` (PII/PHI field classifications)
- **Schema Mappings**: `config/schema-mappings.yaml` (Cassandra → warehouse types)
- **Environment Variables**: `.env` (database credentials, secrets)

## Monitoring

- **Prometheus Metrics**: `http://localhost:9090/metrics`
  - `cdc_events_processed_total{destination, table}`: Events replicated
  - `cdc_replication_lag_seconds{destination}`: Lag behind source
  - `cdc_events_per_second{destination}`: Throughput
  - `cdc_errors_total{destination, error_type}`: Error counts
  - `cdc_backlog_depth{destination}`: Uncommitted events

- **Health Check**: `http://localhost:8080/health`
  - Dependency status (Cassandra, Postgres, ClickHouse, TimescaleDB)
  - Connection latency, uptime

## Documentation

- **Quickstart**: [specs/001-secure-cdc-pipeline/quickstart.md](specs/001-secure-cdc-pipeline/quickstart.md)
- **Architecture Decisions**: [specs/001-secure-cdc-pipeline/research.md](specs/001-secure-cdc-pipeline/research.md)
- **Data Model**: [specs/001-secure-cdc-pipeline/data-model.md](specs/001-secure-cdc-pipeline/data-model.md)
- **API Contracts**: [specs/001-secure-cdc-pipeline/contracts/](specs/001-secure-cdc-pipeline/contracts/)
- **Implementation Plan**: [specs/001-secure-cdc-pipeline/plan.md](specs/001-secure-cdc-pipeline/plan.md)
- **Task Breakdown**: [specs/001-secure-cdc-pipeline/tasks.md](specs/001-secure-cdc-pipeline/tasks.md)

## Constitution & Principles

This project follows strict constitutional principles:

1. **Security-First Architecture** (NON-NEGOTIABLE): TLS, masking, audit logs, secrets management
2. **Multi-Database Compatibility**: Pluggable sinks, declarative schema mappings
3. **Exactly-Once Delivery**: Transactional offsets, idempotent operations
4. **Observable & Debuggable**: Prometheus, JSON logs, OpenTelemetry
5. **Test-Driven Development** (NON-NEGOTIABLE): 80%+ coverage, Red-Green-Refactor
6. **Performance & Scalability**: Asyncio, batching, backpressure
7. **Simplicity & Maintainability**: YAGNI, config over code, minimal deps

See [.specify/memory/constitution.md](.specify/memory/constitution.md) for full details.

## License

MIT License

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow and coding standards.

## Support

- **Issues**: [GitHub Issues](https://github.com/NhaLeTruc/hybrid-cdc-demo/issues)
- **Documentation**: [specs/](specs/)
- **Quickstart**: [quickstart.md](specs/001-secure-cdc-pipeline/quickstart.md)
