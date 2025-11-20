"""
Integration tests for CDC Pipeline startup and initialization
Tests pipeline creation, configuration loading, and component initialization
"""

import pytest
from pathlib import Path

from src.config.settings import CDCSettings, CassandraSettings, DestinationsSettings
from src.main import CDCPipeline


@pytest.mark.asyncio
class TestPipelineStartup:
    """Test CDC Pipeline initialization and startup"""

    def test_pipeline_init_with_default_config(self):
        """Test that pipeline initializes with default configuration"""
        # When: Creating pipeline with default config
        pipeline = CDCPipeline()

        # Then: Pipeline should be initialized
        assert pipeline is not None
        assert pipeline.config is not None
        assert isinstance(pipeline.config, CDCSettings)
        assert pipeline.reader is not None
        assert pipeline.offset_manager is not None
        assert pipeline.sinks == {}  # Sinks not initialized yet
        assert pipeline._shutdown_flag is False

    def test_pipeline_init_with_custom_config(self, tmp_path):
        """Test that pipeline initializes with custom configuration from file"""
        # Given: A custom config file
        config_file = tmp_path / "test_pipeline.yaml"
        config_file.write_text("""
cassandra:
  hosts: ["testhost"]
  port: 9042
  keyspace: "test_keyspace"
  cdc_raw_directory: "/tmp/cdc_raw"

destinations:
  postgres:
    enabled: false
    host: "localhost"
    port: 5432
    database: "test_db"
  clickhouse:
    enabled: false
    host: "localhost"
    port: 9000
    database: "test_db"
  timescaledb:
    enabled: false
    host: "localhost"
    port: 5432
    database: "test_db"

pipeline:
  batch_size: 50
  max_parallelism: 2
  max_in_flight_batches: 5
  poll_interval_ms: 200

retry:
  max_attempts: 3
  base_delay_ms: 50
  max_delay_ms: 5000
  backoff_multiplier: 1.5
  jitter: true

observability:
  metrics_port: 9091
  health_check_port: 8081
  log_level: "DEBUG"
  log_format: "json"
""")

        # When: Creating pipeline with custom config
        pipeline = CDCPipeline(config_path=str(config_file))

        # Then: Pipeline should use custom configuration
        assert pipeline.config.cassandra.hosts == ["testhost"]
        assert pipeline.config.cassandra.keyspace == "test_keyspace"
        assert pipeline.config.pipeline.batch_size == 50
        assert pipeline.config.pipeline.max_parallelism == 2
        assert pipeline.config.retry.max_attempts == 3
        assert pipeline.config.observability.metrics_port == 9091

    async def test_pipeline_initialize_sinks_all_disabled(self):
        """Test sink initialization when all sinks are disabled"""
        # Given: Pipeline with all sinks disabled
        config = CDCSettings(
            cassandra=CassandraSettings(
                hosts=["localhost"],
                keyspace="test",
            ),
            destinations=DestinationsSettings()  # All disabled by default
        )

        # Note: CDCPipeline doesn't accept config parameter yet
        # This test shows what we need to implement
        pipeline = CDCPipeline()
        pipeline.config = config

        # When: Initializing sinks
        await pipeline.initialize_sinks()

        # Then: No sinks should be initialized
        assert len(pipeline.sinks) == 0

    def test_pipeline_shutdown_flag_initial_state(self):
        """Test that shutdown flag is False on initialization"""
        # When: Creating new pipeline
        pipeline = CDCPipeline()

        # Then: Shutdown flag should be False
        assert pipeline._shutdown_flag is False

    def test_pipeline_components_created(self):
        """Test that all required components are created on init"""
        # When: Creating pipeline
        pipeline = CDCPipeline()

        # Then: All core components should exist
        assert hasattr(pipeline, 'config')
        assert hasattr(pipeline, 'reader')
        assert hasattr(pipeline, 'offset_manager')
        assert hasattr(pipeline, 'sinks')
        assert hasattr(pipeline, '_shutdown_flag')


@pytest.mark.asyncio
class TestPipelineConfiguration:
    """Test configuration handling in pipeline"""

    def test_default_cassandra_config(self):
        """Test default Cassandra configuration values"""
        # When: Creating pipeline with defaults
        pipeline = CDCPipeline()

        # Then: Cassandra config should have sensible defaults
        assert pipeline.config.cassandra.hosts == ["localhost"]
        assert pipeline.config.cassandra.port == 9042
        assert pipeline.config.cassandra.cdc_raw_directory == "/var/lib/cassandra/cdc_raw"

    def test_default_pipeline_config(self):
        """Test default pipeline configuration values"""
        # When: Creating pipeline with defaults
        pipeline = CDCPipeline()

        # Then: Pipeline config should have sensible defaults
        assert pipeline.config.pipeline.batch_size == 100
        assert pipeline.config.pipeline.max_parallelism == 4
        assert pipeline.config.pipeline.max_in_flight_batches == 10
        assert pipeline.config.pipeline.poll_interval_ms == 100

    def test_default_retry_config(self):
        """Test default retry configuration values"""
        # When: Creating pipeline with defaults
        pipeline = CDCPipeline()

        # Then: Retry config should have sensible defaults
        assert pipeline.config.retry.max_attempts == 5
        assert pipeline.config.retry.base_delay_ms == 100
        assert pipeline.config.retry.max_delay_ms == 30000
        assert pipeline.config.retry.backoff_multiplier == 2.0
        assert pipeline.config.retry.jitter is True

    def test_default_observability_config(self):
        """Test default observability configuration values"""
        # When: Creating pipeline with defaults
        pipeline = CDCPipeline()

        # Then: Observability config should have sensible defaults
        assert pipeline.config.observability.metrics_port == 9090
        assert pipeline.config.observability.health_check_port == 8080
        assert pipeline.config.observability.log_level == "INFO"
        assert pipeline.config.observability.log_format == "json"
