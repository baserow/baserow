import asyncio
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
