from rest_framework.status import HTTP_404_NOT_FOUND

ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST = (
    "ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The specified AI assistant chat does not exist.",
)


ERROR_ASSISTANT_MODEL_NOT_SUPPORTED = (
    "ERROR_ASSISTANT_MODEL_NOT_SUPPORTED",
    400,
    (
        "The specified language model is not supported or the provided API key is missing/invalid. "
        "Ensure you have set the correct provider API key and selected a compatible model in "
        "`BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL`. See https://docs.litellm.ai/docs/providers for "
        "supported models, required environment variables, and example configuration."
    ),
)
