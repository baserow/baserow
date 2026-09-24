import os
import subprocess
import sys

import pytest


@pytest.mark.websockets
def test_asgi_application_import_initializes_django_in_a_fresh_process():
    # pytest-django initializes the registry before collecting normal WS tests.
    # A real ASGI worker imports the router before config.asgi calls django.setup.
    code = """
from django.apps import apps

assert not apps.ready
from baserow.config.asgi import application

assert apps.ready
assert callable(application.application_mapping["websocket"])
"""
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "baserow.config.settings.test",
        "PYTHONPATH": os.pathsep.join(sys.path),
    }
    result = subprocess.run(  # noqa: S603 - fixed code in the current interpreter.
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
