"""
Retry utility functions for handling LangChain parsing exceptions.
"""

import time
import logging
from typing import Any, Callable, Type, TypeVar
from langchain_core.exceptions import OutputParserException

logger = logging.getLogger(__name__)

T = TypeVar("T")


def invoke_with_retry(
    chain_invoke_func: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    exponential_backoff: bool = True,
    retry_exceptions: tuple[Type[Exception], ...] = (OutputParserException, Exception),
) -> T:
    """
    Invoke a chain with retry logic for handling parsing exceptions.

    Args:
        chain_invoke_func: Function that returns the result of chain.invoke()
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Base delay in seconds between retries (default: 1.0)
        exponential_backoff: Whether to use exponential backoff (default: True)
        retry_exceptions: Tuple of exception types to retry on (default: OutputParserException)

    Returns:
        The result from chain.invoke() if successful

    Raises:
        The last exception encountered if all retries fail
    """

    last_exception = None

    for attempt in range(max_retries + 1):  # +1 for the initial attempt
        try:
            logger.debug(f"Chain invoke attempt {attempt + 1}/{max_retries + 1}")
            return chain_invoke_func()

        except retry_exceptions as e:
            last_exception = e

            if attempt < max_retries:  # Don't sleep after the last attempt
                if exponential_backoff:
                    delay = base_delay * (2**attempt)
                else:
                    delay = base_delay

                logger.warning(
                    f"Chain invoke attempt {attempt + 1} failed with {type(e).__name__}: {str(e)}. "
                    f"Retrying in {delay}s... (attempt {attempt + 2}/{max_retries + 1})"
                )
                time.sleep(delay)
            else:
                logger.error(
                    f"Chain invoke failed after {max_retries + 1} attempts. "
                    f"Final error: {type(e).__name__}: {str(e)}"
                )

        except Exception as e:
            # For non-retry exceptions, fail immediately
            logger.error(
                f"Chain invoke failed with non-retryable exception: {type(e).__name__}: {str(e)}"
            )
            raise

    # If we get here, all retries have been exhausted
    if last_exception:
        raise last_exception
    else:
        raise RuntimeError("Unexpected error: no exception to re-raise")


def invoke_with_progressive_fallback(
    primary_invoke_func: Callable[[], T],
    fallback_invoke_func: Callable[[], T] | None = None,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> T:
    """
    Invoke a chain with retry logic and optional fallback function.

    This is useful when you want to try a more complex schema first,
    then fall back to a simpler schema if parsing continues to fail.

    Args:
        primary_invoke_func: Primary function that returns chain.invoke() result
        fallback_invoke_func: Optional fallback function to try if primary fails
        max_retries: Maximum number of retry attempts per function
        base_delay: Base delay in seconds between retries

    Returns:
        The result from successful invoke function

    Raises:
        The last exception if both primary and fallback fail
    """

    try:
        return invoke_with_retry(
            primary_invoke_func, max_retries=max_retries, base_delay=base_delay
        )
    except (OutputParserException, RuntimeError) as primary_error:
        if fallback_invoke_func is not None:
            logger.warning(
                f"Primary chain invoke failed after retries. Trying fallback function. "
                f"Primary error: {type(primary_error).__name__}: {str(primary_error)}"
            )

            try:
                return invoke_with_retry(
                    fallback_invoke_func, max_retries=max_retries, base_delay=base_delay
                )
            except (OutputParserException, RuntimeError) as fallback_error:
                logger.error(
                    f"Both primary and fallback chain invokes failed. "
                    f"Fallback error: {type(fallback_error).__name__}: {str(fallback_error)}"
                )
                raise fallback_error
        else:
            # No fallback available, re-raise the primary error
            raise primary_error
