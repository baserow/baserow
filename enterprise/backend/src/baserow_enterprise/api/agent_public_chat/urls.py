from django.urls import path

from .views import (
    PublicChatAuthView,
    PublicChatConversationsView,
    PublicChatConversationView,
    PublicChatInfoView,
    PublicChatMessagesView,
    PublicChatStopView,
    PublicChatStreamView,
    PublicChatWidgetScriptView,
)

app_name = "baserow_enterprise.api.agent_public_chat"

urlpatterns = [
    path("<slug:slug>/", PublicChatInfoView.as_view(), name="info"),
    path("<slug:slug>/auth/", PublicChatAuthView.as_view(), name="auth"),
    path(
        "<slug:slug>/conversations/",
        PublicChatConversationsView.as_view(),
        name="conversations",
    ),
    path(
        "<slug:slug>/conversation/",
        PublicChatConversationView.as_view(),
        name="conversation",
    ),
    path(
        "<slug:slug>/conversation/messages/",
        PublicChatMessagesView.as_view(),
        name="messages",
    ),
    path("<slug:slug>/conversation/stop/", PublicChatStopView.as_view(), name="stop"),
    path(
        "<slug:slug>/widget.js",
        PublicChatWidgetScriptView.as_view(),
        name="widget_script",
    ),
]

stream_urlpatterns = [
    path("<slug:slug>/stream/", PublicChatStreamView.as_view(), name="stream"),
]
