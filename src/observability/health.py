"""
Health Check System for CDC Pipeline
Monitors health of Cassandra and all destination warehouses
"""

import asyncio
import json
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Optional, Tuple

import structlog

from src.config.settings import CDCSettings

logger = structlog.get_logger(__name__)


class HealthStatus:
    """
    Tracks health status of all dependencies
    """

    def __init__(self):
        self.dependencies: Dict[str, Dict[str, any]] = {}
        self.start_time = datetime.now(timezone.utc)
        self.version = "1.0.0"

    def update_dependency(self, name: str, status: str, latency_ms: float) -> None:
        """
        Update health status for a dependency

        Args:
            name: Dependency name (cassandra, postgres, clickhouse, timescaledb)
            status: Status ("up" or "down")
            latency_ms: Latency in milliseconds
        """
        self.dependencies[name] = {
            "status": status,
            "latency_ms": round(latency_ms, 2),
            "last_check": datetime.now(timezone.utc).isoformat(),
        }

    def get_overall_status(self) -> str:
        """
        Get overall health status

        Returns:
            "healthy" if all dependencies are up, "unhealthy" otherwise
        """
        if not self.dependencies:
            return "unhealthy"

        all_up = all(dep["status"] == "up" for dep in self.dependencies.values())
        return "healthy" if all_up else "unhealthy"

    def get_uptime_seconds(self) -> float:
        """
        Get pipeline uptime in seconds

        Returns:
            Uptime in seconds
        """
        return (datetime.now(timezone.utc) - self.start_time).total_seconds()

    def to_dict(self) -> Dict:
        """
        Convert health status to dictionary for JSON response

        Returns:
            Dict with status, dependencies, uptime, version
        """
        return {
            "status": self.get_overall_status(),
            "uptime_seconds": round(self.get_uptime_seconds(), 2),
            "version": self.version,
            "dependencies": self.dependencies,
        }


# Global health status instance
_health_status = HealthStatus()


async def check_cassandra_health(
    host: str = "localhost",
    port: int = 9042,
    timeout_seconds: float = 5.0,
) -> Tuple[bool, float]:
    """
    Check Cassandra health

    Args:
        host: Cassandra host
        port: Cassandra port
        timeout_seconds: Timeout for health check

    Returns:
        Tuple of (is_healthy, latency_ms)
    """
    try:
        from cassandra.cluster import Cluster

        start_time = time.time()

        # Create connection and execute simple query
        cluster = Cluster([host], port=port, connect_timeout=timeout_seconds)
        session = cluster.connect()
        session.execute("SELECT now() FROM system.local", timeout=timeout_seconds)

        latency_ms = (time.time() - start_time) * 1000

        session.shutdown()
        cluster.shutdown()

        logger.debug("Cassandra health check passed", latency_ms=latency_ms)
        return (True, latency_ms)

    except Exception as e:
        logger.warning("Cassandra health check failed", error=str(e))
        return (False, 0.0)


async def check_postgres_health(
    connection_url: Optional[str] = None,
    timeout_seconds: float = 5.0,
) -> Tuple[bool, float]:
    """
    Check Postgres health

    Args:
        connection_url: Postgres connection URL
        timeout_seconds: Timeout for health check

    Returns:
        Tuple of (is_healthy, latency_ms)
    """
    try:
        from psycopg import AsyncConnection

        if connection_url is None:
            try:
                config = CDCSettings()
                connection_url = config.destinations.postgres.connection_url
            except Exception as config_error:
                # If config fails to load, use default localhost connection
                logger.debug("Failed to load CDCSettings, using default connection", error=str(config_error))
                connection_url = "postgresql://postgres@localhost:5432/postgres"

        start_time = time.time()

        # Create connection and execute simple query
        async with await AsyncConnection.connect(
            connection_url, connect_timeout=timeout_seconds
        ) as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                await cur.fetchone()

        latency_ms = (time.time() - start_time) * 1000

        logger.debug("Postgres health check passed", latency_ms=latency_ms)
        return (True, latency_ms)

    except Exception as e:
        logger.warning("Postgres health check failed", error=str(e))
        return (False, 0.0)


async def check_clickhouse_health(
    host: str = "localhost",
    port: int = 9000,
    timeout_seconds: float = 5.0,
) -> Tuple[bool, float]:
    """
    Check ClickHouse health

    Args:
        host: ClickHouse host
        port: ClickHouse native port
        timeout_seconds: Timeout for health check

    Returns:
        Tuple of (is_healthy, latency_ms)
    """
    try:
        from clickhouse_driver import Client

        start_time = time.time()

        # Create client and execute simple query
        client = Client(host=host, port=port, connect_timeout=timeout_seconds)
        client.execute("SELECT 1")

        latency_ms = (time.time() - start_time) * 1000

        client.disconnect()

        logger.debug("ClickHouse health check passed", latency_ms=latency_ms)
        return (True, latency_ms)

    except Exception as e:
        logger.warning("ClickHouse health check failed", error=str(e))
        return (False, 0.0)


async def check_timescaledb_health(
    connection_url: Optional[str] = None,
    timeout_seconds: float = 5.0,
) -> Tuple[bool, float]:
    """
    Check TimescaleDB health

    Args:
        connection_url: TimescaleDB connection URL
        timeout_seconds: Timeout for health check

    Returns:
        Tuple of (is_healthy, latency_ms)
    """
    try:
        from psycopg import AsyncConnection

        if connection_url is None:
            try:
                config = CDCSettings()
                connection_url = config.destinations.timescaledb.connection_url
            except Exception as config_error:
                # If config fails to load, use default localhost connection
                logger.debug("Failed to load CDCSettings, using default connection", error=str(config_error))
                connection_url = "postgresql://postgres@localhost:5432/timeseries"

        start_time = time.time()

        # Create connection and check TimescaleDB extension
        async with await AsyncConnection.connect(
            connection_url, connect_timeout=timeout_seconds
        ) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'"
                )
                result = await cur.fetchone()
                if not result:
                    raise Exception("TimescaleDB extension not found")

        latency_ms = (time.time() - start_time) * 1000

        logger.debug("TimescaleDB health check passed", latency_ms=latency_ms)
        return (True, latency_ms)

    except Exception as e:
        logger.warning("TimescaleDB health check failed", error=str(e))
        return (False, 0.0)


async def check_all_dependencies(
    postgres_url: Optional[str] = None,
    timescaledb_url: Optional[str] = None,
) -> Dict[str, Dict[str, any]]:
    """
    Check health of all dependencies concurrently

    Args:
        postgres_url: Optional Postgres connection URL
        timescaledb_url: Optional TimescaleDB connection URL

    Returns:
        Dict mapping dependency name to health status
    """
    logger.info("Running health checks for all dependencies")

    # Run all health checks concurrently
    results = await asyncio.gather(
        check_cassandra_health(),
        check_postgres_health(connection_url=postgres_url),
        check_clickhouse_health(),
        check_timescaledb_health(connection_url=timescaledb_url),
        return_exceptions=True,
    )

    # Process results
    dependencies = {}
    dep_names = ["cassandra", "postgres", "clickhouse", "timescaledb"]

    for dep_name, result in zip(dep_names, results):
        if isinstance(result, Exception):
            dependencies[dep_name] = {"status": "down", "latency_ms": 0.0}
        else:
            is_healthy, latency_ms = result
            dependencies[dep_name] = {
                "status": "up" if is_healthy else "down",
                "latency_ms": latency_ms,
            }

    logger.info(
        "Health check completed",
        healthy_count=sum(1 for d in dependencies.values() if d["status"] == "up"),
    )
    return dependencies


async def update_health_status() -> None:
    """
    Update global health status by checking all dependencies
    """
    dependencies = await check_all_dependencies()

    for dep_name, dep_status in dependencies.items():
        _health_status.update_dependency(
            name=dep_name,
            status=dep_status["status"],
            latency_ms=dep_status["latency_ms"],
        )


def get_health_status() -> Dict:
    """
    Get current health status as dict

    Returns:
        Health status dictionary
    """
    return _health_status.to_dict()


class HealthHTTPHandler(BaseHTTPRequestHandler):
    """
    HTTP handler for /health endpoint
    """

    def do_GET(self):
        """Handle GET requests"""
        if self.path == "/health":
            health_data = get_health_status()

            # Determine HTTP status code
            status_code = 200 if health_data["status"] == "healthy" else 503

            # Send response
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(health_data, indent=2).encode())

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


def start_health_server(port: int = 8080) -> None:
    """
    Start HTTP server for /health endpoint

    Args:
        port: HTTP port to expose /health endpoint
    """
    server = HTTPServer(("0.0.0.0", port), HealthHTTPHandler)

    # Run server in background thread
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    logger.info("Health check server started", port=port)


async def run_periodic_health_checks(interval_seconds: int = 30) -> None:
    """
    Run health checks periodically in the background

    Args:
        interval_seconds: Interval between health checks
    """
    logger.info("Starting periodic health checks", interval_seconds=interval_seconds)

    while True:
        try:
            await update_health_status()
        except Exception as e:
            logger.error("Error running health checks", error=str(e))

        await asyncio.sleep(interval_seconds)
