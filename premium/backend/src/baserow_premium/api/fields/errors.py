from rest_framework.status import HTTP_400_BAD_REQUEST

ERROR_AI_FIELD_PROMPT_INVALID = (
    "ERROR_AI_FIELD_PROMPT_INVALID",
    HTTP_400_BAD_REQUEST,
    "The AI field's prompt is broken: {e}",
)
