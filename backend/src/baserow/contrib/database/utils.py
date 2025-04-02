import time
from functools import wraps
from typing import Any, Callable

from django.db import transaction
from django.db.utils import InternalError

from baserow.contrib.database.exceptions import FailedToCommitTransactionException


def retry_on_transaction_failure(max_retries: int = 3, initial_backoff: float = 0.2):
    """
    Decorator that wraps a function in a transaction.atomic block and retries
    on InternalError errors with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_backoff: Initial backoff time in seconds

    Note:
        Using this decorator requires to ensure that request.data is not modified
        by the function that is decorated.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            retries = 0
            backoff = initial_backoff

            while retries <= max_retries:
                try:
                    with transaction.atomic():
                        return func(*args, **kwargs)
                except InternalError as e:
                    if retries == max_retries:
                        raise FailedToCommitTransactionException() from e
                    time.sleep(backoff)
                    backoff *= 2
                retries += 1

        return wrapper

    return decorator
