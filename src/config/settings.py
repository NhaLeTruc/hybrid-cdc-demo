"""
Pydantic Settings Models for CDC Pipeline Configuration
Based on contracts/config-schema.yaml
"""

from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CassandraSettings(BaseSettings):
    """Cassandra source database configuration"""

    hosts: List[str] = Field(default=["localhost"], description="Cassandra contact points")
    port: int = Field(default=9042, ge=1, le=65535)
    keyspace: str = Field(..., description="Cassandra keyspace to monitor")
    username: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)
    cdc_raw_directory: str = Field(
        default="/var/lib/cassandra/cdc_raw", description="Path to CDC commitlog directory"
    )
    ssl_enabled: bool = Field(default=True)
    ssl_ca_cert: Optional[str] = Field(default=None)

    model_config = SettingsConfigDict(env_prefix="CDC_CASSANDRA_")


class PostgresSettings(BaseSettings):
    """Postgres destination configuration"""

    host: str = Field(default="localhost")
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(..., description="Destination database name")
    username: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)
    ssl_mode: str = Field(default="require", pattern="^(disable|require|verify-ca|verify-full)$")
    connection_pool_size: int = Field(default=10, ge=1, le=100)

    model_config = SettingsConfigDict(env_prefix="CDC_POSTGRES_")


class ClickHouseSettings(BaseSettings):
    """ClickHouse destination configuration"""

    host: str = Field(default="localhost")
    port: int = Field(default=9000, ge=1, le=65535)
    database: str = Field(..., description="Destination database name")
    username: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)
    use_tls: bool = Field(default=True)
    connection_pool_size: int = Field(default=10, ge=1, le=100)

    model_config = SettingsConfigDict(env_prefix="CDC_CLICKHOUSE_")


class TimescaleDBSettings(BaseSettings):
    """TimescaleDB destination configuration (Postgres extension)"""

    host: str = Field(default="localhost")
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(..., description="Destination database name")
    username: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)
    ssl_mode: str = Field(default="require", pattern="^(disable|require|verify-ca|verify-full)$")
    connection_pool_size: int = Field(default=10, ge=1, le=100)

    model_config = SettingsConfigDict(env_prefix="CDC_TIMESCALEDB_")


class DestinationsSettings(BaseSettings):
    """All destination warehouse configurations"""

    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    clickhouse: ClickHouseSettings = Field(default_factory=ClickHouseSettings)
    timescaledb: TimescaleDBSettings = Field(default_factory=TimescaleDBSettings)


class PipelineSettings(BaseSettings):
    """Core pipeline tuning parameters"""

    batch_size: int = Field(default=100, ge=1, le=10000, description="Events per micro-batch")
    max_parallelism: int = Field(default=4, ge=1, le=64, description="Concurrent workers")
    max_in_flight_batches: int = Field(
        default=10, ge=1, le=1000, description="Backpressure control"
    )
    poll_interval_ms: int = Field(
        default=100, ge=10, le=60000, description="Commitlog polling interval (ms)"
    )


class RetrySettings(BaseSettings):
    """Retry and failure handling configuration"""

    max_attempts: int = Field(default=5, ge=1, le=100, description="Max retry attempts")
    base_delay_ms: int = Field(default=100, ge=10, le=10000, description="Initial retry delay")
    max_delay_ms: int = Field(
        default=30000, ge=100, le=300000, description="Maximum retry delay cap"
    )
    backoff_multiplier: float = Field(
        default=2.0, ge=1.0, le=10.0, description="Exponential backoff multiplier"
    )
    jitter: bool = Field(default=True, description="Add random jitter (0-25%)")


class ObservabilitySettings(BaseSettings):
    """Metrics, logging, and tracing configuration"""

    metrics_port: int = Field(default=9090, ge=1024, le=65535)
    metrics_path: str = Field(default="/metrics", pattern=r"^/.*$")
    health_check_port: int = Field(default=8080, ge=1024, le=65535)
    health_check_path: str = Field(default="/health", pattern=r"^/.*$")
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    log_format: str = Field(default="json", pattern="^(json|console)$")
    enable_tracing: bool = Field(default=False)
    tracing_endpoint: Optional[str] = Field(default=None)

    model_config = SettingsConfigDict(env_prefix="CDC_")


class CDCSettings(BaseSettings):
    """Complete CDC pipeline configuration"""

    cassandra: CassandraSettings = Field(default_factory=CassandraSettings)
    destinations: DestinationsSettings = Field(default_factory=DestinationsSettings)
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)
    retry: RetrySettings = Field(default_factory=RetrySettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)

    # Configuration file paths
    config_file: str = Field(default="config/pipeline.yaml", description="Path to main config file")
    masking_rules_file: str = Field(
        default="config/masking-rules.yaml", description="Path to masking rules"
    )
    schema_mappings_file: str = Field(
        default="config/schema-mappings.yaml", description="Path to schema mappings"
    )

    model_config = SettingsConfigDict(
        env_prefix="CDC_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("config_file", "masking_rules_file", "schema_mappings_file")
    @classmethod
    def validate_file_exists(cls, v: str) -> str:
        """Validate that configuration files exist (optional validation)"""
        # Note: File existence validation can be added here if needed
        return v
