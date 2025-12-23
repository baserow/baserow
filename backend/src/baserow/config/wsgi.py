"""
WSGI config for baserow project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/howto/deployment/wsgi/
"""

from django.conf import settings
from django.core.wsgi import get_wsgi_application

from baserow.config.helpers import check_lazy_loaded_libraries
from baserow.core.telemetry.telemetry import setup_logging, setup_telemetry

# The telemetry instrumentation library setup needs to run prior to django's setup.
setup_telemetry(add_django_instrumentation=True)

application = get_wsgi_application()

# It is critical to setup our own logging after django has been setup and done its own
# logging setup. Otherwise Django will try to destroy and log handlers we added prior.
setup_logging()

# This is only needed in asgi.py
settings.BASEROW_LAZY_LOADED_LIBRARIES.append("mcp")

# Check that libraries meant to be lazy-loaded haven't been imported at startup.
# This runs after Django is fully loaded, so it catches imports from all apps.
check_lazy_loaded_libraries()
