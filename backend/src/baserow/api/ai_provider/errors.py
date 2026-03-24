from rest_framework.status import HTTP_404_NOT_FOUND

ERROR_AI_PROVIDER_DOES_NOT_EXIST = (
    "ERROR_AI_PROVIDER_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested AI provider does not exist.",
)

ERROR_AI_PROVIDER_MODEL_DOES_NOT_EXIST = (
    "ERROR_AI_PROVIDER_MODEL_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested AI provider model does not exist.",
)
