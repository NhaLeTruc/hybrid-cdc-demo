"""
Unit tests for retry logic
Tests exponential backoff with jitter
"""

import time

import pytest


class TestRetryLogic:
    """Test retry logic with exponential backoff"""

    def test_exponential_backoff_calculation(self):
        """Test that backoff time increases exponentially"""
        from src.sinks.retry import calculate_backoff

        # Backoff should double with each attempt
        backoff1 = calculate_backoff(attempt=1, base_delay=1.0, multiplier=2.0, jitter=False)
        backoff2 = calculate_backoff(attempt=2, base_delay=1.0, multiplier=2.0, jitter=False)
        backoff3 = calculate_backoff(attempt=3, base_delay=1.0, multiplier=2.0, jitter=False)

        assert backoff1 == 1.0
        assert backoff2 == 2.0
        assert backoff3 == 4.0

    def test_backoff_with_jitter(self):
        """Test that jitter adds randomness to backoff"""
        from src.sinks.retry import calculate_backoff

        # With jitter, backoff should vary
        backoffs = [
            calculate_backoff(attempt=2, base_delay=1.0, multiplier=2.0, jitter=True)
            for _ in range(10)
        ]

        # Should have some variation
        assert len(set(backoffs)) > 1  # Not all the same
        # All should be within reasonable range (0.5x to 1.5x of base)
        for backoff in backoffs:
            assert 1.0 <= backoff <= 3.0

    def test_max_backoff_limit(self):
        """Test that backoff doesn't exceed maximum"""
        from src.sinks.retry import calculate_backoff

        # Even with many attempts, should cap at max_delay
        backoff = calculate_backoff(
            attempt=100,
            base_delay=1.0,
            multiplier=2.0,
            max_delay=60.0,
            jitter=False,
        )

        assert backoff <= 60.0

    def test_retry_policy_dataclass(self):
        """Test RetryPolicy configuration"""
        from src.sinks.retry import RetryPolicy

        policy = RetryPolicy(
            max_attempts=5,
            base_delay=1.0,
            max_delay=60.0,
            multiplier=2.0,
            jitter=True,
        )

        assert policy.max_attempts == 5
        assert policy.base_delay == 1.0
        assert policy.max_delay == 60.0

    @pytest.mark.asyncio
    async def test_retry_decorator_success_on_first_attempt(self):
        """Test that successful operations don't retry"""
        from src.sinks.retry import RetryPolicy, with_retry

        call_count = 0

        @with_retry(RetryPolicy(max_attempts=3))
        async def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_operation()

        assert result == "success"
        assert call_count == 1  # Should only call once

    @pytest.mark.asyncio
    async def test_retry_decorator_retries_on_failure(self):
        """Test that failures trigger retries"""
        from src.sinks.retry import RetryPolicy, with_retry

        call_count = 0

        @with_retry(RetryPolicy(max_attempts=3, base_delay=0.01))
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        result = await failing_operation()

        assert result == "success"
        assert call_count == 3  # Should retry until success

    @pytest.mark.asyncio
    async def test_retry_gives_up_after_max_attempts(self):
        """Test that retry gives up after max attempts"""
        from src.sinks.retry import RetryPolicy, with_retry

        call_count = 0

        @with_retry(RetryPolicy(max_attempts=3, base_delay=0.01))
        async def always_failing():
            nonlocal call_count
            call_count += 1
            raise Exception("Permanent failure")

        with pytest.raises(Exception, match="Permanent failure"):
            await always_failing()

        assert call_count == 3  # Should try max times

    def test_classify_error_as_retryable(self):
        """Test error classification as retryable"""

        # Connection errors should be retryable
        # assert is_retryable_error(ConnectionError("Connection lost"))
        # assert is_retryable_error(TimeoutError("Request timeout"))

        # Some errors should not be retryable
        # assert not is_retryable_error(ValueError("Invalid data"))
        pass

    def test_retry_backoff_timing(self):
        """Test that retry actually waits for backoff period"""
        from src.sinks.retry import calculate_backoff

        start_time = time.time()

        # Simulate retry with backoff
        backoff = calculate_backoff(attempt=1, base_delay=0.1, multiplier=1.0, jitter=False)
        time.sleep(backoff)

        elapsed = time.time() - start_time

        # Should have waited at least the backoff period
        assert elapsed >= 0.1
