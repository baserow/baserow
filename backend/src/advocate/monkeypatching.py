import contextlib
import os.path
import socket
import traceback


class DisallowedConnectException(Exception):
    pass


class CheckedSocket(socket.socket):
    CONNECT_ALLOWED_FUNCS = {"validating_create_connection"}
    # `test_testserver.py` makes raw connections to the test server to ensure it works
    CONNECT_ALLOWED_FILES = {"test_testserver.py"}
    _checks_enabled = True

    @classmethod
    @contextlib.contextmanager
    def bypass_checks(cls):
        try:
            cls._checks_enabled = False
            yield
        finally:
            cls._checks_enabled = True

    @classmethod
    def _check_frame_allowed(cls, frame):
        if os.path.basename(frame[0]) in cls.CONNECT_ALLOWED_FILES:
            return True
        if frame[2] in cls.CONNECT_ALLOWED_FUNCS:
            return True
        return False

    def connect(self, *args, **kwargs):
        if self._checks_enabled:
            stack = traceback.extract_stack()
            if not any(self._check_frame_allowed(frame) for frame in stack):
                raise DisallowedConnectException("calling socket.connect() unsafely!")
        return super().connect(*args, **kwargs)
