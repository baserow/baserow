from django.urls import path

from baserow.contrib.integrations.core.api.webhooks.views import CoreHTTPWebhookView

app_name = "baserow.contrib.integrations.core.api.webhooks"

urlpatterns = [
    path(
        r"webhooks/<uuid:webhook_uid>/",
        CoreHTTPWebhookView.as_view(),
        name="http_webhook",
    ),
]
