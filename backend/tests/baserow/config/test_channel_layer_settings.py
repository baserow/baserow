import json
import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "settings_module, redis_url, expected_timeout",
    [
        ("base", "redis://localhost:6379/0", 10),
        ("base", "rediss://localhost:6379/0", 10),
        ("base", "redis://localhost:6379/0?socket_timeout=30", 30),
        ("heroku", "rediss://localhost:6379/0", 10),
    ],
)
def test_channel_socket_timeout_exceeds_blocking_receive(
    settings_module, redis_url, expected_timeout
):
    # Settings are evaluated at import time. A fresh interpreter also prevents the
    # Heroku settings from mutating the base settings used by other tests.
    result = subprocess.run(  # noqa: S603 - fixed code in the current interpreter.
        [
            sys.executable,
            "-c",
            """
import importlib
import json
import os

from channels_redis.core import RedisChannelLayer
from channels_redis.utils import create_pool, decode_hosts

settings = importlib.import_module(os.environ["CHANNEL_SETTINGS_MODULE"])
host = decode_hosts(settings.CHANNEL_LAYERS["default"]["CONFIG"]["hosts"])[0]
pool = create_pool(host)
connection = pool.connection_class(**pool.connection_kwargs)
print(json.dumps({
    "socket_timeout": connection.socket_timeout,
    "blocking_timeout": RedisChannelLayer.brpop_timeout,
}))
""",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join(sys.path),
            "CHANNEL_SETTINGS_MODULE": f"baserow.config.settings.{settings_module}",
            "REDIS_URL": redis_url,
            "REDIS_TLS_URL": redis_url,
        },
    )

    assert result.returncode == 0, result.stderr
    timeouts = json.loads(result.stdout)
    assert timeouts["socket_timeout"] == expected_timeout
    assert timeouts["socket_timeout"] > timeouts["blocking_timeout"]
