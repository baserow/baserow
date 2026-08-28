from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

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
ERROR_AI_PROVIDER_TYPE_NOT_SUPPORTED = (
    "ERROR_AI_PROVIDER_TYPE_NOT_SUPPORTED",
    HTTP_400_BAD_REQUEST,
    "The requested AI provider type is not supported.",
)
ERROR_AI_PROVIDER_TYPE_ALREADY_CONFIGURED = (
    "ERROR_AI_PROVIDER_TYPE_ALREADY_CONFIGURED",
    HTTP_400_BAD_REQUEST,
    "That AI provider type is already configured.",
)
ERROR_AI_PROVIDER_MODEL_ALREADY_CONFIGURED = (
    "ERROR_AI_PROVIDER_MODEL_ALREADY_CONFIGURED",
    HTTP_400_BAD_REQUEST,
    "That model identifier is already configured for this provider.",
)
ERROR_AI_PROVIDER_IS_READ_ONLY = (
    "ERROR_AI_PROVIDER_IS_READ_ONLY",
    HTTP_400_BAD_REQUEST,
    "Inherited instance AI providers are read-only in a workspace.",
)
ERROR_INVALID_AI_PROVIDER_SETTINGS = (
    "ERROR_INVALID_AI_PROVIDER_SETTINGS",
    HTTP_400_BAD_REQUEST,
    "The AI provider settings are invalid.",
)
ERROR_AI_PROVIDER_MODEL_IN_USE = (
    "ERROR_AI_PROVIDER_MODEL_IN_USE",
    HTTP_400_BAD_REQUEST,
    "This model is selected by an AI feature. Choose another model for that feature first.",
)
ERROR_AI_PROVIDER_FEATURE_MODEL_NOT_AVAILABLE = (
    "ERROR_AI_PROVIDER_FEATURE_MODEL_NOT_AVAILABLE",
    HTTP_400_BAD_REQUEST,
    "The selected model is not available to this AI feature at this scope.",
)
ERROR_AI_PROVIDER_FEATURE_MODE_NOT_ALLOWED = (
    "ERROR_AI_PROVIDER_FEATURE_MODE_NOT_ALLOWED",
    HTTP_400_BAD_REQUEST,
    "The requested AI feature setting mode is not allowed.",
)
ERROR_AI_PROVIDER_MODEL_FEATURE_TYPE_DOES_NOT_EXIST = (
    "ERROR_AI_PROVIDER_MODEL_FEATURE_TYPE_DOES_NOT_EXIST",
    HTTP_400_BAD_REQUEST,
    "The requested AI model feature type does not exist.",
)
