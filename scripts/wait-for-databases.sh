#!/bin/bash
# Wait for all databases to be ready before starting the CDC pipeline
# Usage: ./scripts/wait-for-databases.sh

set -e

echo "⏳ Waiting for databases to be ready..."

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Timeout settings (seconds)
TIMEOUT=120
INTERVAL=2

# Database connection details from environment or defaults
CASSANDRA_HOST=${CASSANDRA_HOST:-localhost}
CASSANDRA_PORT=${CASSANDRA_PORT:-9042}

POSTGRES_HOST=${POSTGRES_HOST:-localhost}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_USER=${POSTGRES_USER:-postgres}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-postgres}
POSTGRES_DB=${POSTGRES_DB:-warehouse}

CLICKHOUSE_HOST=${CLICKHOUSE_HOST:-localhost}
CLICKHOUSE_PORT=${CLICKHOUSE_PORT:-8123}

TIMESCALEDB_HOST=${TIMESCALEDB_HOST:-localhost}
TIMESCALEDB_PORT=${TIMESCALEDB_PORT:-5433}
TIMESCALEDB_USER=${TIMESCALEDB_USER:-postgres}
TIMESCALEDB_PASSWORD=${TIMESCALEDB_PASSWORD:-postgres}
TIMESCALEDB_DB=${TIMESCALEDB_DB:-warehouse}

# ============================================================================
# Cassandra Health Check
# ============================================================================
wait_for_cassandra() {
    echo -e "${YELLOW}Checking Cassandra at ${CASSANDRA_HOST}:${CASSANDRA_PORT}...${NC}"
    local elapsed=0

    while [ $elapsed -lt $TIMEOUT ]; do
        if timeout 5 bash -c "echo > /dev/tcp/${CASSANDRA_HOST}/${CASSANDRA_PORT}" 2>/dev/null; then
            echo -e "${GREEN}✓ Cassandra is ready${NC}"
            return 0
        fi

        sleep $INTERVAL
        elapsed=$((elapsed + INTERVAL))
        echo -e "${YELLOW}  Waiting for Cassandra... (${elapsed}s/${TIMEOUT}s)${NC}"
    done

    echo -e "${RED}✗ Cassandra failed to start within ${TIMEOUT}s${NC}"
    return 1
}

# ============================================================================
# Postgres Health Check
# ============================================================================
wait_for_postgres() {
    echo -e "${YELLOW}Checking Postgres at ${POSTGRES_HOST}:${POSTGRES_PORT}...${NC}"
    local elapsed=0

    while [ $elapsed -lt $TIMEOUT ]; do
        # Try psql first if available
        if command -v psql >/dev/null 2>&1; then
            if PGPASSWORD="${POSTGRES_PASSWORD}" psql \
                -h "${POSTGRES_HOST}" \
                -p "${POSTGRES_PORT}" \
                -U "${POSTGRES_USER}" \
                -d "${POSTGRES_DB}" \
                -c "SELECT 1;" >/dev/null 2>&1; then
                echo -e "${GREEN}✓ Postgres is ready${NC}"
                return 0
            fi
        else
            # Fallback to TCP check if psql is not available
            if timeout 5 bash -c "echo > /dev/tcp/${POSTGRES_HOST}/${POSTGRES_PORT}" 2>/dev/null; then
                echo -e "${GREEN}✓ Postgres is ready (TCP check only - install psql for full verification)${NC}"
                return 0
            fi
        fi

        sleep $INTERVAL
        elapsed=$((elapsed + INTERVAL))
        echo -e "${YELLOW}  Waiting for Postgres... (${elapsed}s/${TIMEOUT}s)${NC}"
    done

    echo -e "${RED}✗ Postgres failed to start within ${TIMEOUT}s${NC}"
    return 1
}

# ============================================================================
# ClickHouse Health Check
# ============================================================================
wait_for_clickhouse() {
    echo -e "${YELLOW}Checking ClickHouse at ${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT}...${NC}"
    local elapsed=0

    while [ $elapsed -lt $TIMEOUT ]; do
        if curl -s "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT}/ping" >/dev/null 2>&1; then
            echo -e "${GREEN}✓ ClickHouse is ready${NC}"
            return 0
        fi

        sleep $INTERVAL
        elapsed=$((elapsed + INTERVAL))
        echo -e "${YELLOW}  Waiting for ClickHouse... (${elapsed}s/${TIMEOUT}s)${NC}"
    done

    echo -e "${RED}✗ ClickHouse failed to start within ${TIMEOUT}s${NC}"
    return 1
}

# ============================================================================
# TimescaleDB Health Check
# ============================================================================
wait_for_timescaledb() {
    echo -e "${YELLOW}Checking TimescaleDB at ${TIMESCALEDB_HOST}:${TIMESCALEDB_PORT}...${NC}"
    local elapsed=0

    while [ $elapsed -lt $TIMEOUT ]; do
        # Try psql first if available
        if command -v psql >/dev/null 2>&1; then
            if PGPASSWORD="${TIMESCALEDB_PASSWORD}" psql \
                -h "${TIMESCALEDB_HOST}" \
                -p "${TIMESCALEDB_PORT}" \
                -U "${TIMESCALEDB_USER}" \
                -d "${TIMESCALEDB_DB}" \
                -c "SELECT 1;" >/dev/null 2>&1; then
                echo -e "${GREEN}✓ TimescaleDB is ready${NC}"
                return 0
            fi
        else
            # Fallback to TCP check if psql is not available
            if timeout 5 bash -c "echo > /dev/tcp/${TIMESCALEDB_HOST}/${TIMESCALEDB_PORT}" 2>/dev/null; then
                echo -e "${GREEN}✓ TimescaleDB is ready (TCP check only - install psql for full verification)${NC}"
                return 0
            fi
        fi

        sleep $INTERVAL
        elapsed=$((elapsed + INTERVAL))
        echo -e "${YELLOW}  Waiting for TimescaleDB... (${elapsed}s/${TIMEOUT}s)${NC}"
    done

    echo -e "${RED}✗ TimescaleDB failed to start within ${TIMEOUT}s${NC}"
    return 1
}

# ============================================================================
# Main
# ============================================================================
main() {
    local all_healthy=true

    # Check all databases
    wait_for_cassandra || all_healthy=false
    wait_for_postgres || all_healthy=false
    wait_for_clickhouse || all_healthy=false
    wait_for_timescaledb || all_healthy=false

    if [ "$all_healthy" = true ]; then
        echo -e "\n${GREEN}🎉 All databases are ready!${NC}\n"
        return 0
    else
        echo -e "\n${RED}❌ Some databases failed to start${NC}\n"
        return 1
    fi
}

# Run main function
main
