import math
import os
import resource
import selectors
import signal
import time
import warnings
from typing import Callable


class LimitedProcessFailed(Exception):
    """Raised if a function in a limited process fails or exceeds its limits."""


def _limit_memory(max_memory_bytes: int):
    # The process already uses the memory of the parent it's forked from, so the
    # limit is on top of that.
    try:
        with open("/proc/self/statm") as statm:
            used_bytes = int(statm.read().split()[0]) * resource.getpagesize()
    except OSError:
        # Only Linux exposes the used memory, which is where Baserow runs.
        return
    limit = used_bytes + max_memory_bytes
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def run_in_limited_process(
    function: Callable[[], bytes], timeout_seconds: float, max_memory_bytes: int
) -> bytes:
    """
    Runs a function in a forked process, which is the only way to stop work that
    takes too much time or memory, like parsing a hostile file. The function must
    only do computations, because the process shares the open connections of the
    parent.

    :param function: The function to run, which returns the result as bytes.
    :param timeout_seconds: The seconds after which the process is stopped.
    :param max_memory_bytes: The memory that the function may use.
    :return: The result of the function.
    :raises LimitedProcessFailed: If the function raised an exception, or exceeded
        the time or memory limit.
    """

    read_fd, write_fd = os.pipe()
    with warnings.catch_warnings():
        # Forking while other threads hold a lock can make the process hang, which
        # the timeout stops.
        warnings.simplefilter("ignore", DeprecationWarning)
        pid = os.fork()

    if pid == 0:
        exit_code = 1
        try:
            os.close(read_fd)
            # Stops the process even if the parent is killed before it can do so.
            signal.signal(signal.SIGALRM, signal.SIG_DFL)
            signal.alarm(math.ceil(timeout_seconds) + 1)
            _limit_memory(max_memory_bytes)
            result = function()
            with os.fdopen(write_fd, "wb") as pipe:
                pipe.write(result)
            exit_code = 0
        finally:
            # Never returns to the code of the parent, and skips its exit handlers,
            # like closing the shared connections.
            os._exit(exit_code)

    os.close(write_fd)
    deadline = time.monotonic() + timeout_seconds
    output = bytearray()
    end_of_output = False
    finished = False
    try:
        with (
            os.fdopen(read_fd, "rb", buffering=0) as pipe,
            selectors.DefaultSelector() as selector,
        ):
            selector.register(pipe, selectors.EVENT_READ)
            while not end_of_output and (remaining := deadline - time.monotonic()) > 0:
                if selector.select(timeout=remaining):
                    chunk = pipe.read(65536)
                    end_of_output = not chunk
                    output += chunk
        if not end_of_output:
            raise LimitedProcessFailed(f"Timed out after {timeout_seconds} seconds.")
        _, status = os.waitpid(pid, 0)
        finished = True
    finally:
        if not finished:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)

    if os.waitstatus_to_exitcode(status) != 0:
        raise LimitedProcessFailed("Failed or exceeded the memory limit.")
    return bytes(output)
