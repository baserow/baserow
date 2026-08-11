from pydantic import BaseModel, Field
from pydantic_ai import Agent

from baserow_enterprise.assistant.model_profiles import (
    SUGGESTIONS,
    get_model_settings,
    get_model_string,
)
from baserow_enterprise.assistant.retrying_model import RetryingModel

ONBOARDING_SUGGESTIONS_INSTRUCTIONS = """\
<identity>
You suggest the first database someone should build in Baserow, based on where \
they work and what they do.
</identity>

<rules>
1. Every prompt is written as if the user typed it themselves: "Track ...", \
"Keep an overview of ...". Never address the user, never mention Baserow, AI, \
tables, fields or views.
2. Keep each prompt to 2 or 3 short sentences, about 35 words. It must be \
readable at a glance.
3. Say what is tracked and name a handful of the details that belong to it. \
Nothing more.
4. Suggest work that this specific team, in this specific industry, actually \
does. Generic ideas that would fit any company are a failure.
5. Every suggestion must cover a different area of their work. Do not offer \
variations of the same idea.
6. Order them by how obviously useful they are, most useful first.
7. `name` is a label of at most four words that describes what is tracked.
8. Use plain, everyday language. No jargon, no buzzwords.
</rules>
"""


class OnboardingPromptSuggestion(BaseModel):
    name: str = Field(description="Label of at most four words.")
    prompt: str = Field(
        description="2 to 3 short sentences describing the database to build."
    )


class OnboardingPromptSuggestions(BaseModel):
    suggestions: list[OnboardingPromptSuggestion]


onboarding_suggestions_agent: Agent[None, OnboardingPromptSuggestions] = Agent(
    output_type=OnboardingPromptSuggestions,
    instructions=ONBOARDING_SUGGESTIONS_INSTRUCTIONS,
    retries=2,
    name="onboarding_suggestions_agent",
)


def generate_onboarding_prompt_suggestions(
    industry: str,
    team: str,
    language: str,
    amount: int = 4,
) -> list[OnboardingPromptSuggestion]:
    """
    Asks the language model for `amount` database ideas tailored to the answers
    given during the onboarding.

    :param industry: The industry the user works in.
    :param team: The team the user is part of.
    :param language: ISO 639-1 code the suggestions must be written in.
    :param amount: How many suggestions to ask for.
    :return: The suggestions, most useful first.
    """

    user_prompt = (
        f"Industry: {industry or 'unknown'}\n"
        f"Team: {team or 'unknown'}\n\n"
        f"Suggest exactly {amount} databases this person could build. "
        f"Write every name and prompt in the language with ISO 639-1 code "
        f"'{language}'."
    )

    model_string = get_model_string()
    result = onboarding_suggestions_agent.run_sync(
        user_prompt,
        model=RetryingModel(model_string),
        model_settings=get_model_settings(model_string, SUGGESTIONS),
    )
    return result.output.suggestions[:amount]
