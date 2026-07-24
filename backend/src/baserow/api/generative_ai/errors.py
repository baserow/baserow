from rest_framework.status import HTTP_400_BAD_REQUEST

ERROR_GENERATIVE_AI_DOES_NOT_EXIST = (
    "ERROR_GENERATIVE_AI_DOES_NOT_EXIST",
    HTTP_400_BAD_REQUEST,
    "The requested generative AI does not exist.",
)
ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE = (
    "ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE",
    HTTP_400_BAD_REQUEST,
    "The selected AI model is disabled or no longer available.",
)
ERROR_GENERATIVE_AI_PROMPT = (
    "ERROR_GENERATIVE_AI_PROMPT",
    HTTP_400_BAD_REQUEST,
    "Something went wrong prompting the model",
)
