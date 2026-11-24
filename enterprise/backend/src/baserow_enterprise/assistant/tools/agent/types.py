"""The setup of an Agent as Kuma's agent tools take it."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.api.validators import no_url_validation
from baserow.contrib.agent.triggers.trigger_types import ROWS_TRIGGER_TYPES
from baserow.contrib.agent.validators import AGENT_TEXT_MAX_LENGTH

SCHEDULE_TRIGGER = "periodic"
WEBHOOK_TRIGGER = "http_trigger"
TRIGGER_TYPES = (*ROWS_TRIGGER_TYPES, WEBHOOK_TRIGGER, SCHEDULE_TRIGGER)
ACTION_TYPES = ("smtp_email", "http_request")
# The periodic service stores the day as a number, Monday first.
WEEKDAYS = (
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
    "SUNDAY",
)
IDENTITY_NAME_MAX_LENGTH = 150

TRIGGER_MESSAGE = (
    "Leave blank so each run opens with the event, such as the rows that changed. "
    "Text here replaces the event, and the Agent no longer knows which rows "
    "changed."
)


class NewIdentity(BaseModel):
    """An identity gets the lowest workspace role that covers the Agent's tools."""

    name: str = Field(
        max_length=IDENTITY_NAME_MAX_LENGTH,
        description="The identity's name, usually the Agent's name. No links.",
    )

    @field_validator("name")
    @classmethod
    def _like_the_identities_api(cls, name: str) -> str:
        try:
            no_url_validation(name)
        except DRFValidationError as exc:
            raise ValueError("An identity's name can't contain a link.") from exc
        return name


class Schedule(BaseModel):
    interval: Literal["MINUTE", "HOUR", "DAY", "WEEK", "MONTH"]
    hour: int = Field(default=9, ge=0, le=23)
    minute: int = Field(
        default=0,
        ge=0,
        le=59,
        description="The minute past the hour; for MINUTE, every how many minutes.",
    )
    day_of_week: Literal[WEEKDAYS] | None = Field(  # type: ignore[valid-type]
        default=None, description="Required for WEEK."
    )
    day_of_month: int | None = Field(
        default=None, ge=1, le=31, description="Required for MONTH."
    )
    timezone: str | None = Field(
        default=None,
        description="The IANA timezone hour and minute are in. Defaults to the "
        "user's timezone.",
    )

    @model_validator(mode="after")
    def _names_its_day(self) -> "Schedule":
        if self.interval == "WEEK" and self.day_of_week is None:
            raise ValueError("A WEEK schedule needs day_of_week.")
        if self.interval == "MONTH" and self.day_of_month is None:
            raise ValueError("A MONTH schedule needs day_of_month.")
        return self

    def service_values(self) -> dict[str, Any]:
        """:return: The schedule as the periodic service stores it."""

        values = self.model_dump(exclude_none=True)
        if self.day_of_week is not None:
            values["day_of_week"] = WEEKDAYS.index(self.day_of_week)
        return values


class RowsTrigger(BaseModel):
    """Runs the Agent when rows of a table are created, updated or deleted."""

    type: Literal[ROWS_TRIGGER_TYPES]  # type: ignore[valid-type]
    table_id: int = Field(description="The watched table, from list_tables.")
    message: str = Field(default="", description=TRIGGER_MESSAGE)

    def service_values(self) -> dict[str, Any]:
        return {"table_id": self.table_id}


class ScheduleTrigger(BaseModel):
    """Runs the Agent on a schedule."""

    type: Literal["periodic"]
    schedule: Schedule
    message: str = Field(default="", description=TRIGGER_MESSAGE)

    def service_values(self) -> dict[str, Any]:
        return self.schedule.service_values()


class WebhookTrigger(BaseModel):
    """Runs the Agent on a webhook request."""

    type: Literal["http_trigger"]
    message: str = Field(default="", description=TRIGGER_MESSAGE)

    def service_values(self) -> dict[str, Any]:
        return {}


TriggerSpec = Annotated[
    RowsTrigger | ScheduleTrigger | WebhookTrigger, Field(discriminator="type")
]


class ActionSpec(BaseModel):
    type: Literal[ACTION_TYPES] = Field(  # type: ignore[valid-type]
        description="smtp_email sends an email; http_request calls a URL."
    )
    name: str = Field(
        pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$",
        description="The tool name the Agent calls: up to 64 letters, numbers and "
        "underscores, starting with a letter or underscore.",
    )
    description: str = Field(default="", description="When the Agent should use it.")


class AgentSetup(BaseModel):
    """An Agent's setup, or the part of it to change. Unset values stay as they are."""

    name: str | None = Field(default=None, description="Required to create.")
    instructions: str | None = Field(
        default=None,
        max_length=AGENT_TEXT_MAX_LENGTH,
        description="What the Agent does, naming the real tables and fields.",
    )
    run_as_identity_id: int | None = Field(
        default=None,
        description="An existing identity the Agent acts as, from list_agent_tools.",
    )
    new_identity: NewIdentity | None = Field(
        default=None,
        description="Create an identity for the Agent to act as. Only when "
        "list_agent_tools says the user can create one.",
    )
    grant_tools: list[str] = Field(
        default_factory=list,
        description="Tools to allow, from list_agent_tools. The Agent's other "
        "tools stay as they are. A tool that changes data asks first.",
    )
    revoke_tools: list[str] = Field(
        default_factory=list, description="Allowed tools to take away."
    )
    provider_type: str | None = Field(
        default=None,
        description="With model_identifier, a model from list_agent_tools. Unset "
        "on a new Agent picks the first enabled model.",
    )
    model_identifier: str | None = None
    web_search_enabled: bool | None = None
    web_fetch_enabled: bool | None = Field(
        default=None,
        description="Only false: the user turns web fetch on in the Agent's "
        "Configuration.",
    )
    add_triggers: list[TriggerSpec] = Field(
        default_factory=list,
        description="Added turned off: the user turns a trigger on in the "
        "Agent's Configuration.",
    )
    turn_off_triggers: list[int] = Field(
        default_factory=list, description="The trigger_id of each trigger to turn off."
    )
    remove_triggers: list[int] = Field(
        default_factory=list,
        description="The trigger_id of each trigger to delete. To change when a "
        "trigger runs, remove it and add the new one in the same call.",
    )
    add_actions: list[ActionSpec] = Field(
        default_factory=list,
        description="Added turned off: the user enters credentials and the "
        "recipient or URL in the Agent's Configuration, then turns them on.",
    )
    remove_actions: list[int] = Field(
        default_factory=list, description="The action_id of each action to delete."
    )

    @model_validator(mode="after")
    def _acts_as_one_identity(self) -> "AgentSetup":
        if self.new_identity and self.run_as_identity_id:
            raise ValueError("Send run_as_identity_id or new_identity, not both.")
        return self
