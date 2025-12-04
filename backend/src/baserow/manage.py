#!/usr/bin/env python
import os
import sys


def enable_debugger():
    """Enable the debugger if the environment variable is set."""

    debugger_enabled = bool(os.environ.get("BASEROW_BACKEND_DEBUGGER_ENABLED"))
    if debugger_enabled:
        import debugpy

        debugger_port = int(os.environ.get("BASEROW_BACKEND_DEBUGGER_PORT", 5678))
        debugpy.listen(("0.0.0.0", debugger_port))  # noqa: S104
        print(f"Debugger attached! Listening on 0.0.0.0:{debugger_port}")


def main():
    from django.conf import settings

    if settings.DEBUG and os.environ.get("RUN_MAIN"):
        enable_debugger()

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
