from importlib.resources import files

from django.conf import settings
from django.http import FileResponse, Http404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page, never_cache
from django.views.decorators.http import require_safe

from drf_spectacular.views import SpectacularJSONAPIView as ParentSpectacularJSONAPIView


@require_safe
def redoc_asset(request, filename):
    content_types = {
        "redoc.standalone.js": "text/javascript",
        "redoc.standalone.js.LICENSE.txt": "text/plain",
        "redoc.standalone.js.map": "application/json",
    }
    if filename not in content_types:
        raise Http404

    # Backend-only deployments do not collect or serve Django static files.
    asset = files("drf_spectacular_sidecar").joinpath(
        "static/drf_spectacular_sidecar/redoc/bundles", filename
    )
    return FileResponse(asset.open("rb"), content_type=content_types[filename])


@method_decorator(
    cache_page(60 * 60 * 24 * 7) if not settings.DEBUG else never_cache, name="dispatch"
)
class CachedSpectacularJSONAPIView(ParentSpectacularJSONAPIView):
    """
    The spectacular view is cached because it contains a memory leak, and because
    it's quite heavy to generate the JSON spec.

    The cache timeout is set at 7 days because if the user updates to another Baserow
    version, the older cache entries must not be left dangling. The response is only
    cached if settings.DEBUG is False, because it can be confusing for other devs if
    their changes are not applied in the schema.
    """
