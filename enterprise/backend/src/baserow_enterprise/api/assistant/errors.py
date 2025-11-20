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

ERROR_CANNOT_SUBMIT_MESSAGE_FEEDBACK = (
    "ERROR_CANNOT_SUBMIT_MESSAGE_FEEDBACK",
    HTTP_400_BAD_REQUEST,
    "This message cannot be submitted for feedback because it has no associated prediction.",
)
