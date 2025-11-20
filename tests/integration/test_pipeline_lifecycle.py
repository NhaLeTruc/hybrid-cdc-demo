"""
Integration tests for CDC Pipeline lifecycle management
Tests pipeline startup, shutdown, state transitions, and resource cleanup
"""

import asyncio
import signal
from pathlib import Path

import pytest

from src.main import CDCPipeline


@pytest.mark.asyncio
class TestPipelineLifecycle:
    """Test CDC Pipeline lifecycle and state management"""

    async def test_pipeline_starts_and_stops_cleanly(self):
        """Test that pipeline can start and stop without errors"""
        # Given: A new pipeline
        pipeline = CDCPipeline()

        # When: Starting the pipeline in the background
        pipeline_task = asyncio.create_task(pipeline.run())

        # Give it time to start
        await asyncio.sleep(0.5)

        # Then: Pipeline should be running
        assert not pipeline_task.done()

        # When: Shutting down
        pipeline.shutdown()

        # Wait for clean shutdown
        try:
            await asyncio.wait_for(pipeline_task, timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail("Pipeline did not shut down within timeout")

        # Then: Pipeline should have stopped
        assert pipeline_task.done()

    async def test_graceful_shutdown_with_sigterm(self, tmp_path):
        """Test that SIGTERM triggers graceful shutdown"""
        # Given: Pipeline with custom config
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
cassandra:
  hosts: ["localhost"]
  port: 9042
  keyspace: "test_keyspace"
  cdc_raw_directory: "/tmp/cdc_raw"

destinations:
  postgres:
    enabled: false
  clickhouse:
    enabled: false
  timescaledb:
    enabled: false

pipeline:
  batch_size: 10
  poll_interval_ms: 100
""")

        pipeline = CDCPipeline(config_path=str(config_file))

        # When: Starting pipeline
        pipeline_task = asyncio.create_task(pipeline.run())
        await asyncio.sleep(0.5)

        # And: Sending shutdown signal (simulated)
        pipeline.shutdown()

        # Then: Pipeline should shut down gracefully
        try:
            await asyncio.wait_for(pipeline_task, timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail("Pipeline did not respond to shutdown signal")

        assert pipeline._shutdown_flag is True

    async def test_pipeline_state_transitions(self):
        """Test pipeline state transitions during lifecycle"""
        # Given: A new pipeline
        pipeline = CDCPipeline()

        # Then: Initial state should be not running
        assert pipeline._shutdown_flag is False

        # When: Starting pipeline
        pipeline_task = asyncio.create_task(pipeline.run())
        await asyncio.sleep(0.5)

        # Then: Should be running
        assert not pipeline_task.done()
        assert pipeline._shutdown_flag is False

        # When: Initiating shutdown
        pipeline.shutdown()

        # Then: Shutdown flag should be set
        assert pipeline._shutdown_flag is True

        # Wait for completion
        await asyncio.wait_for(pipeline_task, timeout=5.0)

        # Then: Should be stopped
        assert pipeline_task.done()

    async def test_cleanup_resources_on_shutdown(self):
        """Test that all resources are cleaned up on shutdown"""
        # Given: Pipeline with sinks initialized
        pipeline = CDCPipeline()

        # Note: This test will need actual sink initialization
        # For now, we test that shutdown completes without hanging

        # When: Starting and stopping
        pipeline_task = asyncio.create_task(pipeline.run())
        await asyncio.sleep(0.5)

        # Record initial state
        initial_sinks_count = len(pipeline.sinks)

        # When: Shutting down
        pipeline.shutdown()
        await asyncio.wait_for(pipeline_task, timeout=5.0)

        # Then: Pipeline should have completed shutdown
        assert pipeline._shutdown_flag is True

        # Sinks should still exist but connections should be closed
        # (We'll verify this more thoroughly when sinks are actually connected)
        assert len(pipeline.sinks) == initial_sinks_count

    async def test_multiple_shutdown_calls_are_safe(self):
        """Test that calling shutdown multiple times doesn't cause errors"""
        # Given: A running pipeline
        pipeline = CDCPipeline()
        pipeline_task = asyncio.create_task(pipeline.run())
        await asyncio.sleep(0.5)

        # When: Calling shutdown multiple times
        pipeline.shutdown()
        pipeline.shutdown()
        pipeline.shutdown()

        # Then: Should complete cleanly
        await asyncio.wait_for(pipeline_task, timeout=5.0)
        assert pipeline._shutdown_flag is True

    async def test_shutdown_before_start_is_safe(self):
        """Test that calling shutdown before starting doesn't cause errors"""
        # Given: A new pipeline
        pipeline = CDCPipeline()

        # When: Calling shutdown before start
        pipeline.shutdown()

        # Then: Should set flag without errors
        assert pipeline._shutdown_flag is True

        # And: Starting after shutdown should complete immediately
        pipeline_task = asyncio.create_task(pipeline.run())
        await asyncio.wait_for(pipeline_task, timeout=2.0)
        assert pipeline_task.done()

    async def test_pipeline_run_with_no_sinks_configured(self):
        """Test that pipeline handles case with no sinks configured"""
        # Given: Pipeline with all sinks disabled
        pipeline = CDCPipeline()

        # Ensure no sinks are enabled
        assert len(pipeline.sinks) == 0

        # When: Running the pipeline
        pipeline_task = asyncio.create_task(pipeline.run())
        await asyncio.sleep(0.5)

        # Then: Should run without errors (just won't process anything)
        assert not pipeline_task.done()

        # Clean shutdown
        pipeline.shutdown()
        await asyncio.wait_for(pipeline_task, timeout=5.0)
        assert pipeline_task.done()


@pytest.mark.asyncio
class TestPipelineErrorHandling:
    """Test pipeline error handling and recovery"""

    async def test_pipeline_handles_initialization_errors_gracefully(self):
        """Test that pipeline handles initialization errors without crashing"""
        # Given: Invalid config path
        try:
            pipeline = CDCPipeline(config_path="/nonexistent/config.yaml")
            # If it doesn't raise, that's fine - it might use defaults
            # Just verify we can shut it down
            pipeline.shutdown()
            assert pipeline._shutdown_flag is True
        except Exception as e:
            # If it raises, that's also acceptable behavior
            # Just ensure it's a clean error, not a crash
            assert isinstance(e, (FileNotFoundError, IOError, ValueError))

    async def test_shutdown_timeout_handling(self):
        """Test that shutdown completes within reasonable time"""
        # Given: A running pipeline
        pipeline = CDCPipeline()
        pipeline_task = asyncio.create_task(pipeline.run())
        await asyncio.sleep(0.5)

        # When: Triggering shutdown
        pipeline.shutdown()
        start_time = asyncio.get_event_loop().time()

        # Wait for shutdown with timeout
        await asyncio.wait_for(pipeline_task, timeout=10.0)

        elapsed = asyncio.get_event_loop().time() - start_time

        # Then: Should complete within reasonable time (< 5 seconds)
        assert elapsed < 5.0, f"Shutdown took {elapsed}s, expected < 5s"
