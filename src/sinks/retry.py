"""
Retry Logic with Exponential Backoff
Handles transient failures with configurable retry policies
"""

import asyncio
import random
from dataclasses import dataclass
from typing import Callable, TypeVar, Optional
import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")


@dataclass
class RetryPolicy:
    """
    Retry policy configuration

    Attributes:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds for first retry
        max_delay: Maximum delay in seconds
        multiplier: Multiplier for exponential backoff
        jitter: Whether to add random jitter to delays
    """

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    multiplier: float = 2.0
    jitter: bool = True


def calculate_backoff(
    attempt: int,
    base_delay: float,
    multiplier: float,
    max_delay: Optional[float] = None,
    jitter: bool = True,
) -> float:
    """
    Calculate backoff delay for retry attempt

    Args:
        attempt: Retry attempt number (1-indexed)
        base_delay: Base delay in seconds
        multiplier: Exponential multiplier
        max_delay: Maximum delay in seconds
        jitter: Whether to add random jitter

    Returns:
        Delay in seconds
    """
    # Exponential backoff: base_delay * (multiplier ^ (attempt - 1))
    delay = base_delay * (multiplier ** (attempt - 1))

    # Cap at max_delay
    if max_delay is not None:
        delay = min(delay, max_delay)

    # Add jitter (±25%)
    if jitter:
        jitter_range = delay * 0.25
        delay = delay + random.uniform(-jitter_range, jitter_range)

    return max(0.0, delay)  # Never negative


def is_retryable_error(error: Exception) -> bool:
    """
    Classify error as retryable or permanent

    Args:
        error: Exception to classify

    Returns:
        True if error is retryable, False if permanent
    """
    # Connection errors are retryable
    if isinstance(error, (ConnectionError, TimeoutError)):
        return True

    # Check for specific database errors
    error_str = str(error).lower()

    # Retryable patterns
    retryable_patterns = [
        "connection",
        "timeout",
        "temporary",
        "unavailable",
        "network",
        "unreachable",
        "refused",
        "reset",
        "broken pipe",
    ]

    for pattern in retryable_patterns:
        if pattern in error_str:
            return True

    # Permanent patterns
    permanent_patterns = [
        "permission denied",
        "authentication failed",
        "syntax error",
        "invalid",
        "does not exist",
    ]

    for pattern in permanent_patterns:
        if pattern in error_str:
            return False

    # Default: treat as retryable for safety
    return True


def with_retry(policy: RetryPolicy):
    """
    Decorator to add retry logic to async functions

    Args:
        policy: Retry policy configuration

    Usage:
        @with_retry(RetryPolicy(max_attempts=5))
        async def risky_operation():
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(1, policy.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    # Check if error is retryable
                    if not is_retryable_error(e):
                        logger.error(
                            "Permanent error, not retrying",
                            error=str(e),
                            function=func.__name__,
                        )
                        raise

                    # Check if we have more attempts
                    if attempt >= policy.max_attempts:
                        logger.error(
                            "Max retry attempts reached",
                            attempts=attempt,
                            error=str(e),
                            function=func.__name__,
                        )
                        raise

                    # Calculate backoff
                    delay = calculate_backoff(
                        attempt=attempt,
                        base_delay=policy.base_delay,
                        multiplier=policy.multiplier,
                        max_delay=policy.max_delay,
                        jitter=policy.jitter,
                    )

                    logger.warning(
                        "Retrying after error",
                        attempt=attempt,
                        max_attempts=policy.max_attempts,
                        delay_seconds=round(delay, 2),
                        error=str(e),
                        function=func.__name__,
                    )

                    # Wait before retry
                    await asyncio.sleep(delay)

            # Should not reach here, but raise last exception if we do
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


async def retry_with_policy(
    func: Callable[..., T],
    policy: RetryPolicy,
    *args,
    **kwargs,
) -> T:
    """
    Execute function with retry policy

    Args:
        func: Async function to execute
        policy: Retry policy
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Function result

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await func(*args, **kwargs)

        except Exception as e:
            last_exception = e

            if not is_retryable_error(e) or attempt >= policy.max_attempts:
                raise

            delay = calculate_backoff(
                attempt=attempt,
                base_delay=policy.base_delay,
                multiplier=policy.multiplier,
                max_delay=policy.max_delay,
                jitter=policy.jitter,
            )

            logger.warning(
                "Retrying after error",
                attempt=attempt,
                delay_seconds=round(delay, 2),
                error=str(e),
            )

            await asyncio.sleep(delay)

    if last_exception:
        raise last_exception
