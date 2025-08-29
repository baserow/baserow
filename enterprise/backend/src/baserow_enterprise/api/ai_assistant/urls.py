from django.urls import path

from .views import AiAssistantChatsView, AiAssistantChatView

app_name = "baserow_enterprise.api.ai_assistant"

urlpatterns = [
    path(
        "chat/<uuid:chat_uuid>/messages/",
        AiAssistantChatView.as_view(),
        name="chat_messages",
    ),
    path(
        "chat/",
        AiAssistantChatsView.as_view(),
        name="list",
    ),
]
