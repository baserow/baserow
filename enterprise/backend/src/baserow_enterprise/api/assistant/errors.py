from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST = (
    "ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The specified AI assistant chat does not exist.",
)


ERROR_ASSISTANT_MODEL_NOT_SUPPORTED = (
    "ERROR_ASSISTANT_MODEL_NOT_SUPPORTED",
    HTTP_400_BAD_REQUEST,
    (
        "The specified language model is not supported or the provided API key is missing/invalid. "
        "Ensure you have set the correct provider API key and selected a compatible model in "
        "`BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL`. See https://baserow.io/docs/installation/ai-assistant for "
        "supported models, required environment variables, and example configuration."
    ),
)

ERROR_ASSISTANT_CONFIGURED_MODEL_NOT_AVAILABLE = (
    "ERROR_ASSISTANT_CONFIGURED_MODEL_NOT_AVAILABLE",
    HTTP_400_BAD_REQUEST,
    (
        "The Kuma model selected in AI provider settings could not be used. "
        "Test the selected model and verify its provider credentials before trying "
        "again."
    ),
)

ERROR_ASSISTANT_MODEL_DISABLED = (
    "ERROR_ASSISTANT_MODEL_DISABLED",
    HTTP_400_BAD_REQUEST,
    ("Kuma is disabled in AI provider settings. Enable Kuma before trying again."),
)

ERROR_CANNOT_SUBMIT_MESSAGE_FEEDBACK = (
    "ERROR_CANNOT_SUBMIT_MESSAGE_FEEDBACK",
    HTTP_400_BAD_REQUEST,
    "This message cannot be submitted for feedback because it has no associated prediction.",
)
