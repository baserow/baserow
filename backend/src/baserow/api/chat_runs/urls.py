from django.urls import path

from .views import ChatRunCancelView, ChatRunView

app_name = "baserow.api.chat_runs"

urlpatterns = [
    path("<uuid:run_id>/", ChatRunView.as_view(), name="detail"),
    path("<uuid:run_id>/cancel/", ChatRunCancelView.as_view(), name="cancel"),
]
