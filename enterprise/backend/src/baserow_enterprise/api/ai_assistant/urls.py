"""URL configuration for AI assistant API endpoints."""
from django.urls import path

from .views import AIAssistantChatView, AIAssistantChatsView, AIAssistantChatUndoView

app_name = "baserow_enterprise.api.ai_assistant"

urlpatterns = [
    path("chat/<uuid:chat_uid>/", AIAssistantChatView.as_view(), name="item"),
    path("chat/", AIAssistantChatsView.as_view(), name="list"),
    path("chat/<uuid:chat_uid>/undo/", AIAssistantChatUndoView.as_view(), name="undo"),
]
