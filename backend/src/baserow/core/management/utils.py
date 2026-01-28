import curses

# Using subprocess for a debug manual command is safe and poses no security risk.
import subprocess  # nosec
import sys
from typing import List, Optional

from django.core.management import CommandError


def run_command_concurrently(
    command: List[str], concurrency: int, header: Optional[str] = None
):
    """
    Launches the provided command in many parallel subprocesses and waits for all to
    finish. Uses curses library to correctly show each subprocesses stderr (which
    tqdm logs on) on its own row so you can see the progress of each all at once.

    :param command: The command to run the subprocess. WARNING: Do not provide
        untrusted user input in this variable it will be executed as a subprocess.
    :param concurrency: The number of subprocesses to launch.
    :param header: An optional header shown above the per subprocess log lines.

    :raises CommandError: When a subprocess fails a command error will be raised.
    """

    child_processes = []
    error_processes = []
    if header is None:
        header = f"Running '{' '.join(command)}' in {concurrency} subprocesses:"

    for i in range(concurrency):
        # Only used by management commands so safe to Popen
        p = subprocess.Popen(  # noqa: S603
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True,
        )
        child_processes.append(p)

    scr = curses.initscr()

    try:
        while child_processes:
            scr.addstr(0, 0, header)
            new_child_processes = []
            for i, cp in enumerate(child_processes):
                if cp.poll() is None:
                    out = cp.stderr.readline().strip().replace("\r", "")
                    scr.addstr(i + 1, 0, out)
                    new_child_processes.append(cp)
                else:
                    if cp.returncode != 0:
                        error_processes.append(cp)
            child_processes = new_child_processes
            scr.refresh()
    finally:
        curses.endwin()

    if error_processes:
        print(f"Errors from subprocesses were (they will be mixed due to concurrency):")
        for error_process in error_processes:
            print(error_process.stderr.read(), file=sys.stderr)
        raise CommandError(
            "The following child processes exited with a non-zero "
            f"error code: {[cp.pid for cp in error_processes]}. See above for their "
            f"reported errors."
        )
