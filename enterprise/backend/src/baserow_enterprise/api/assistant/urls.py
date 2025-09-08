from django.urls import path

from .views import AssistantChatsView, AssistantChatView

app_name = "baserow_enterprise.api.assistant"

urlpatterns = [
    path(
        "chat/<uuid:chat_uuid>/messages/",
        AssistantChatView.as_view(),
        name="chat_messages",
    ),
    path(
        "chat/",
        AssistantChatsView.as_view(),
        name="list",
    ),
]
