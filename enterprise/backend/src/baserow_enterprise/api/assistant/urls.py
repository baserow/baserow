from django.urls import path

from .views import (
    AssistantChatMessageFeedbackView,
    AssistantChatsView,
    AssistantChatView,
    AssistantOnboardingPromptSuggestionsView,
)

app_name = "baserow_enterprise.api.assistant"

urlpatterns = [
    path(
        "chat/<uuid:chat_uuid>/messages/",
        AssistantChatView.as_view(),
        name="chat_messages",
    ),
    path(
        "chat/<uuid:chat_uuid>/cancel/",
        AssistantChatView.as_view(),
        name="cancel_message",
    ),
    path(
        "chat/",
        AssistantChatsView.as_view(),
        name="list",
    ),
    path(
        "messages/<int:message_id>/feedback/",
        AssistantChatMessageFeedbackView.as_view(),
        name="message_feedback",
    ),
    path(
        "onboarding/prompt-suggestions/",
        AssistantOnboardingPromptSuggestionsView.as_view(),
        name="onboarding_prompt_suggestions",
    ),
]
