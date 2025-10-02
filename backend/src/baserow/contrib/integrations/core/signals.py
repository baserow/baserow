from django.dispatch import Signal, receiver

from baserow.contrib.integrations.core.api.webhooks.views import get_error_cache_key
from baserow.contrib.integrations.core.models import CoreHTTPWebhookService
from baserow.core.cache import global_cache

core_http_webhook_service_updated = Signal()


@receiver(core_http_webhook_service_updated)
def invalidate_error_cache_key(sender, service: CoreHTTPWebhookService, **kwargs):
    for i in [True, False]:
        cache_key = get_error_cache_key(service.uid, i)
        global_cache.invalidate(cache_key)
