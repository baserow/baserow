import os

# Allow Django ORM calls from async test functions. Mirrors
# `backend/tests/baserow/ws/conftest.py` — async ws handlers use
# `database_sync_to_async` in production, but tests bypass that wrapper
# by awaiting the handler directly.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
