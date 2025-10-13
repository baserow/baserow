from functools import wraps

from baserow.config.db_routers import clear_db_state, set_write_mode


def manage_db_state(fn=None, *, write_first: bool = False):
    """
    Ensures each Celery task starts and ends with a clean DB router state.
    Defaults to read-replica. First write pins to writer for remainder of task.

    If write_first=True, pin to writer immediately at task start.
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            clear_db_state()
            if write_first:
                set_write_mode()
            try:
                return f(*args, **kwargs)
            finally:
                clear_db_state()

        return wrapper

    return decorator if fn is None else decorator(fn)
