from django.urls import include, path

from baserow.core.registries import Plugin


class IntegrationsPlugin(Plugin):
    """Registers the API endpoints shared by several integration types."""

    type = "integrations"

    def get_api_urls(self):
        from baserow.contrib.integrations.oauth_account.api import (
            urls as oauth_account_urls,
        )

        return [
            path(
                "integrations/oauth/",
                include(oauth_account_urls, namespace="oauth_account"),
            )
        ]
