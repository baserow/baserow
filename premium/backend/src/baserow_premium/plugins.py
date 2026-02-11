from django.urls import include, path

from baserow.core.registries import Plugin
from baserow_premium.api import urls as api_urls
from baserow_premium.license.plugin import LicensePlugin


class PremiumPlugin(Plugin):
    type = "premium"

    def get_api_urls(self):
        return [
            path("", include(api_urls, namespace=self.type)),
        ]

    def get_license_plugin(self, cache_queries: bool = False) -> LicensePlugin:
        return LicensePlugin(cache_queries)
