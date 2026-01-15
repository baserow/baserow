import asyncio
import os
import sys

from django.conf import settings

from loguru import logger


def check_lazy_loaded_libraries():
    """
    Check if any libraries that should be lazy-loaded have been imported at startup.

    This function checks sys.modules against settings.BASEROW_LAZY_LOADED_LIBRARIES
    and emits a warning if any of them have been loaded prematurely. This helps
    catch accidental top-level imports that defeat the purpose of lazy loading
    these heavy libraries to reduce memory footprint.

    Only runs when DEBUG is True.
    """

    if not settings.DEBUG:
        return

    lazy_libs = getattr(settings, "BASEROW_LAZY_LOADED_LIBRARIES", [])
    loaded_early = []

    for lib in lazy_libs:
        if lib in sys.modules:
            loaded_early.append(lib)

    if loaded_early:
        libs_list = ", ".join(f'"{lib}"' for lib in loaded_early)
        logger.warning(
            f"The following libraries were loaded during startup but should be "
            f"lazy-loaded to reduce memory footprint: {', '.join(loaded_early)}. "
            f"Either import them inside functions/methods where they're used, or "
            f"remove them from BASEROW_LAZY_LOADED_LIBRARIES if they're legitimately "
            f"needed at startup. "
            f"To debug, add the following code at the very top of your settings file "
            f"(e.g., settings/dev.py, before any other imports):\n\n"
            f"import sys, traceback\n"
            f"class _T:\n"
            f"    def find_module(self, n, p=None):\n"
            f"        for lib in [{libs_list}]:\n"
            f"            if n == lib or n.startswith(lib + '.'):\n"
            f"                print(f'IMPORT: {{n}}'); traceback.print_stack(); sys.exit(1)\n"
            f"        return None\n"
            f"sys.meta_path.insert(0, _T())\n"
        )


class dummy_context:
    async def __aenter__(self):
        pass

    async def __aexit__(self, exc_type, exc, traceback):
        pass


class ConcurrencyLimiterASGI:
    """
    Helper wrapper on ASGI app to limit the number of requests handled
    at the same time.
    """

    def __init__(self, app, max_concurrency: int | None = None):
        self.app = app
        logger.info(f"Setting ASGI app concurrency to {max_concurrency}")
        self.semaphore = (
            asyncio.Semaphore(max_concurrency)
            if (isinstance(max_concurrency, int) and max_concurrency > 0)
            else dummy_context()
        )

    async def __call__(self, scope, receive, send):
        async with self.semaphore:
            await self.app(scope, receive, send)


def log_env_warnings():
    from django.conf import settings

    if settings.BASEROW_PUBLIC_URL:
        if settings.BASEROW_PUBLIC_URL.startswith("http://localhost"):
            logger.warning(
                "WARNING: Baserow is configured to use a BASEROW_PUBLIC_URL of "
                f"{settings.BASEROW_PUBLIC_URL}. If you attempt to access Baserow on "
                "any other hostname requests to the backend will fail as they will be "
                "from an unknown host. "
                "Please set BASEROW_PUBLIC_URL if you will be accessing Baserow "
                f"from any other URL then {settings.BASEROW_PUBLIC_URL}."
            )
    else:
        if "PUBLIC_BACKEND_URL" not in os.environ:
            logger.warning(
                "WARNING: Baserow is configured to use a PUBLIC_BACKEND_URL of "
                f"{settings.PUBLIC_BACKEND_URL}. If you attempt to access Baserow on any other "
                "hostname requests to the backend will fail as they will be from an "
                "unknown host."
                "Please ensure you set PUBLIC_BACKEND_URL if you will be accessing "
                f"Baserow from any other URL then {settings.PUBLIC_BACKEND_URL}."
            )
        if "PUBLIC_WEB_FRONTEND_URL" not in os.environ:
            logger.warning(
                "WARNING: Baserow is configured to use a default PUBLIC_WEB_FRONTEND_URL "
                f"of {settings.PUBLIC_WEB_FRONTEND_URL}. Emails sent by Baserow will use links "
                f"pointing to {settings.PUBLIC_WEB_FRONTEND_URL} when telling users how to "
                "access your server. "
                "If this is incorrect please ensure you have set PUBLIC_WEB_FRONTEND_URL to "
                "the URL where users can access your Baserow server."
            )
