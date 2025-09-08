from django.urls import include, path

from baserow.core.registries import Plugin
from baserow_enterprise.api import urls as api_urls
from baserow_enterprise.api.assistant import urls as assistant_urls


class EnterprisePlugin(Plugin):
    type = "enterprise"

    def get_api_urls(self):
        return [
            path("", include(api_urls, namespace=self.type)),
        ]

    def get_urls(self):
        return [
            path("assistant/", include(assistant_urls, namespace="assistant")),
        ]
