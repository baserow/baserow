from functools import lru_cache

import dspy
from litellm import get_supported_openai_params

from baserow_enterprise.assistant.exceptions import AssistantModelNotSupportedError


@lru_cache(maxsize=1)
def ensure_llm_model_accessible(lm: dspy.LM) -> None:
    """
    Ensure the given model is accessible and works with the current API key and
    settings.

    :param model: The model name to validate.
    :raises AssistantModelNotSupportedError: If the model is not supported or not
        accessible.
    """

    params = get_supported_openai_params(lm.model)
    if params is None:
        raise AssistantModelNotSupportedError(
            f"The model '{lm.model}' is not supported or could not be found."
        )

    with dspy.context(lm=lm):
        try:
            lm("Say ok if you can read this.")
        except Exception as e:
            raise AssistantModelNotSupportedError(
                f"The model '{lm.model}' is not supported or accessible: {e}"
            ) from e
