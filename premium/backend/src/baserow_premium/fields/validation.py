from __future__ import annotations

from typing import TYPE_CHECKING

from baserow.core.generative_ai.exceptions import (
    MODEL_NOT_AVAILABLE_MESSAGE,
    GenerativeAITypeDoesNotExist,
)
from baserow.core.generative_ai.registries import generative_ai_model_type_registry

from .visitors import get_ai_prompt_error

if TYPE_CHECKING:
    from .models import AIField


def get_ai_model_error(ai_field: AIField) -> str | None:
    """
    Return an error if the model configured on the AI field is unavailable.

    Workspace-level settings take precedence in ``get_enabled_models``, matching
    the model resolution used when values are generated.
    """

    try:
        model_type = generative_ai_model_type_registry.get(
            ai_field.ai_generative_ai_type
        )
    except GenerativeAITypeDoesNotExist:
        return MODEL_NOT_AVAILABLE_MESSAGE

    workspace = ai_field.table.database.workspace
    if ai_field.ai_generative_ai_model not in model_type.get_enabled_models(workspace):
        return MODEL_NOT_AVAILABLE_MESSAGE
    return None


def get_ai_field_error(ai_field: AIField) -> str | None:
    """Return the first configuration error that must block AI generation."""

    if not ai_field.table_id:
        return None
    return get_ai_prompt_error(ai_field.ai_prompt, ai_field.table_id) or (
        get_ai_model_error(ai_field)
    )
