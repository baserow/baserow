"""
Run callbacks when the outermost deferred callback context exits.

Written for imports, where some work can only be done once everything has been
imported. Example:

    from baserow.core.deferred_callbacks import deferred_callback_context

    with deferred_callback_context():
        deferred_callback_context.register(do_something)
"""

from collections import deque
from contextlib import contextmanager
from typing import Callable, Deque, Generator, Optional

from asgiref.local import Local

# Not the `local_cache`: it stores nothing when `BASEROW_USE_LOCAL_CACHE` is off,
# so every registration would think no context is active.
_state = Local()


def _get_callbacks() -> Optional[Deque[Callable[[], None]]]:
    return getattr(_state, "callbacks", None)


def register_deferred_callback(callback: Callable[[], None]) -> None:
    """
    Registers a callback to run when the active callback context exits.

    :param callback: The callback to run, taking no arguments.
    :raises RuntimeError: When no context is active. Loud on purpose, so a
        caller learns its entry point is missing one.
    """

    callbacks = _get_callbacks()
    if callbacks is None:
        raise RuntimeError(
            "Deferred callbacks can only be registered inside "
            "deferred_callback_context()."
        )

    callbacks.append(callback)


class DeferredCallbackContext:
    register = staticmethod(register_deferred_callback)

    @contextmanager
    def __call__(self) -> Generator[None, None, None]:
        """
        Runs the registered callbacks when the outermost context exits.

        A nested context registers into its outer one. Callbacks run in
        registration order, and only when the block completes: a block that
        raised leaves half-imported rows, which is nothing to run against. A
        callback may register more work, which runs after everything before it.
        """

        is_outermost_context = _get_callbacks() is None
        if is_outermost_context:
            _state.callbacks = deque()

        try:
            yield
        except Exception:
            if is_outermost_context:
                _state.callbacks = None
            raise

        if is_outermost_context:
            callbacks = _state.callbacks
            try:
                # Drained, not iterated, so a callback can register more work.
                while callbacks:
                    callbacks.popleft()()
            finally:
                _state.callbacks = None


deferred_callback_context = DeferredCallbackContext()
