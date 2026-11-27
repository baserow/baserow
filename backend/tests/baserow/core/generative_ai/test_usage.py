import logging
from unittest.mock import patch

from django.test.utils import override_settings

import pytest
from asgiref.sync import async_to_sync
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import RequestUsage

from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel
from baserow.core.generative_ai.exceptions import GenerativeAIPromptError
from baserow.core.generative_ai.generative_ai_model_types import (
    OpenAIGenerativeAIModelType,
)
from baserow.core.generative_ai.usage import (
    AIUsage,
    AIUsageLimitExceeded,
    AIUsageScope,
    UsageReportingModel,
    ai_request_completed,
    ai_request_starting,
    ai_usage_context,
    ai_usage_preparing,
    get_ai_usage_plugin_data,
    notify_ai_usage_preparing,
)
from baserow.core.models import Workspace
from baserow.core.registries import Plugin, plugin_registry

MODEL = "gpt-test"
REQUEST_USAGE = RequestUsage(input_tokens=120, output_tokens=30, cache_read_tokens=20)


def scope_in_context(provider_type, model, **kwargs):
    return AIUsageScope(
        provider_type,
        model,
        kwargs.pop("uses_shared_key", False),
        **kwargs,
    ).with_usage_context()


def respond(messages, info):
    return ModelResponse(parts=[TextPart(content="Hello")], usage=REQUEST_USAGE)


async def respond_streamed(messages, info):
    yield "Hello"


class Recorder:
    """Connects to the usage signals and records what they send."""

    def __init__(self, refuse_with=None):
        self.started = []
        self.completed = []
        self.refuse_with = refuse_with

    def on_starting(self, sender, scope, **kwargs):
        self.started.append(scope)
        if self.refuse_with:
            raise self.refuse_with

    def on_completed(self, sender, scope, usage, **kwargs):
        self.completed.append((scope, usage))

    def __enter__(self):
        ai_request_starting.connect(self.on_starting)
        ai_request_completed.connect(self.on_completed)
        return self

    def __exit__(self, *args):
        ai_request_starting.disconnect(self.on_starting)
        ai_request_completed.disconnect(self.on_completed)


def create_provider(workspace=None, models=(MODEL,)):
    provider = AIProviderConfig.objects.create(
        workspace=workspace, provider_type="openai", api_key="key"
    )
    for model in models:
        AIProviderModel.objects.create(provider_config=provider, model_identifier=model)
    return provider


def test_ai_usage_from_pydantic_ai():
    assert AIUsage.from_pydantic_ai(None) == AIUsage()
    usage = AIUsage.from_pydantic_ai(REQUEST_USAGE)
    assert usage == AIUsage(input_tokens=120, output_tokens=30, cache_read_tokens=20)
    # A method, like the `usage()` of some pydantic-ai results.
    assert AIUsage.from_pydantic_ai(lambda: REQUEST_USAGE) == usage


def test_ai_usage_context_is_nested_and_reset():
    assert scope_in_context("openai", MODEL).feature is None

    with ai_usage_context(feature="some_feature", reference_id=1):
        with ai_usage_context(reference_type="ai_field"):
            scope = scope_in_context("openai", MODEL)
            assert scope.feature == "some_feature"
            assert (scope.reference_type, scope.reference_id) == ("ai_field", "1")
        assert scope_in_context("openai", MODEL).reference_type is None

    assert scope_in_context("openai", MODEL).feature is None


def test_the_context_tells_whose_explicit_credentials_are_used():
    assert scope_in_context("openai", MODEL).uses_shared_key is False

    with ai_usage_context(uses_shared_key=True):
        assert scope_in_context("openai", MODEL).uses_shared_key is True


def test_requests_can_be_marked_as_made_without_the_database():
    assert scope_in_context("openai", MODEL).database_allowed is True

    with ai_usage_context(database_allowed=False):
        with ai_usage_context(feature="some_feature"):
            assert scope_in_context("openai", MODEL).database_allowed is False

    assert scope_in_context("openai", MODEL).database_allowed is True


def test_notify_ai_usage_preparing_tells_the_workspace_and_feature():
    workspace = Workspace(id=1)
    received = []

    def receiver(sender, **kwargs):
        received.append(kwargs)

    ai_usage_preparing.connect(receiver)
    try:
        notify_ai_usage_preparing(workspace, "other_feature")
    finally:
        ai_usage_preparing.disconnect(receiver)

    assert received == [
        {
            "signal": ai_usage_preparing,
            "workspace": workspace,
            "feature": "other_feature",
        }
    ]


@pytest.mark.django_db
def test_resolve_model_settings_tells_whose_credentials_are_used(data_fixture):
    workspace = data_fixture.create_workspace()
    model_type = OpenAIGenerativeAIModelType()

    explicit = model_type.resolve_model_settings(
        MODEL, workspace, settings_override={"api_key": "x", "models": [MODEL]}
    )
    assert explicit.uses_shared_key is False

    assert model_type.resolve_model_settings(MODEL, None).uses_shared_key is True

    create_provider()
    instance = model_type.resolve_model_settings(MODEL, workspace)
    assert instance.uses_shared_key is True
    assert instance.settings["api_key"] == "key"

    # The provider state is cached per workspace, so another one is used.
    other_workspace = data_fixture.create_workspace()
    create_provider(workspace=other_workspace)
    owned = model_type.resolve_model_settings(MODEL, other_workspace)
    assert owned.uses_shared_key is False
    # The old method returns the same settings.
    assert (
        model_type.get_model_settings_override(MODEL, other_workspace) == owned.settings
    )


@pytest.mark.django_db
def test_an_inactive_workspace_provider_uses_the_instance_credentials(data_fixture):
    workspace = data_fixture.create_workspace()
    workspace_provider = create_provider(workspace=workspace)
    workspace_provider.is_active = False
    workspace_provider.save()
    # Without the model, so the provider getters resolve the credentials.
    create_provider(models=["other-model"])

    resolved = OpenAIGenerativeAIModelType().resolve_model_settings(MODEL, workspace)

    assert resolved.settings is None
    assert resolved.uses_shared_key is True


@pytest.mark.django_db
@override_settings(BASEROW_OPENAI_API_KEY="env-key", BASEROW_OPENAI_MODELS=[MODEL])
def test_resolve_model_settings_with_environment_credentials(data_fixture):
    workspace = data_fixture.create_workspace()

    resolved = OpenAIGenerativeAIModelType().resolve_model_settings(MODEL, workspace)

    assert resolved.uses_shared_key is True
    assert resolved.settings["api_key"] == "env-key"


@pytest.mark.django_db
def test_prompt_reports_the_usage(data_fixture):
    workspace = data_fixture.create_workspace()
    create_provider()
    model_type = OpenAIGenerativeAIModelType()

    with (
        patch.object(model_type, "get_ai_model", return_value=FunctionModel(respond)),
        Recorder() as recorder,
        ai_usage_context(feature="some_feature", reference_id=7),
    ):
        assert model_type.prompt(MODEL, "Hi", workspace=workspace) == "Hello"

    (scope,) = recorder.started
    assert scope.provider_type == "openai"
    assert scope.model == MODEL
    assert scope.uses_shared_key is True
    assert scope.feature == "some_feature"
    assert scope.workspace == workspace
    assert scope.reference_id == "7"
    ((completed_scope, usage),) = recorder.completed
    assert completed_scope == scope
    assert (usage.input_tokens, usage.output_tokens, usage.cache_read_tokens) == (
        120,
        30,
        20,
    )


@pytest.mark.django_db
def test_a_refused_prompt_never_reaches_the_model(data_fixture):
    workspace = data_fixture.create_workspace()
    model_type = OpenAIGenerativeAIModelType()

    model = FunctionModel(respond)
    with (
        patch.object(model_type, "get_ai_model", return_value=model),
        patch.object(model, "request", wraps=model.request) as request,
        Recorder(refuse_with=AIUsageLimitExceeded("No credits left.")) as recorder,
        pytest.raises(GenerativeAIPromptError) as raised,
    ):
        model_type.prompt(
            MODEL,
            "Hi",
            workspace=workspace,
            settings_override={"api_key": "x", "models": [MODEL]},
        )

    request.assert_not_called()
    assert isinstance(raised.value, AIUsageLimitExceeded)
    assert str(raised.value) == "No credits left."
    assert recorder.completed == []


@pytest.mark.django_db
def test_a_failing_completed_receiver_does_not_fail_the_prompt(data_fixture):
    model_type = OpenAIGenerativeAIModelType()

    def fail(sender, **kwargs):
        raise RuntimeError("charging failed")

    ai_request_completed.connect(fail)
    try:
        with patch.object(
            model_type, "get_ai_model", return_value=FunctionModel(respond)
        ):
            assert (
                model_type.prompt(
                    MODEL, "Hi", settings_override={"api_key": "x", "models": [MODEL]}
                )
                == "Hello"
            )
    finally:
        ai_request_completed.disconnect(fail)


@pytest.mark.django_db
def test_a_failing_starting_receiver_does_not_fail_the_prompt(data_fixture):
    model_type = OpenAIGenerativeAIModelType()

    def fail(sender, **kwargs):
        raise KeyError("bug in a usage receiver")

    ai_request_starting.connect(fail)
    try:
        with patch.object(
            model_type, "get_ai_model", return_value=FunctionModel(respond)
        ):
            assert (
                model_type.prompt(
                    MODEL, "Hi", settings_override={"api_key": "x", "models": [MODEL]}
                )
                == "Hello"
            )
    finally:
        ai_request_starting.disconnect(fail)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("signal", [ai_request_starting, ai_request_completed])
def test_a_failing_query_of_a_receiver_keeps_the_transaction_usable(
    data_fixture, signal
):
    from django.db import connection, transaction

    model_type = OpenAIGenerativeAIModelType()

    def fail(sender, **kwargs):
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM this_table_does_not_exist")

    signal.connect(fail)
    try:
        with (
            transaction.atomic(),
            patch.object(
                model_type, "get_ai_model", return_value=FunctionModel(respond)
            ),
        ):
            assert (
                model_type.prompt(
                    MODEL, "Hi", settings_override={"api_key": "x", "models": [MODEL]}
                )
                == "Hello"
            )
            # The transaction can still be used.
            assert Workspace.objects.count() >= 0
    finally:
        signal.disconnect(fail)


@pytest.mark.django_db(transaction=True)
def test_a_refusal_keeps_what_the_receiver_stored(data_fixture):
    from django.db import transaction

    model_type = OpenAIGenerativeAIModelType()

    def refuse(sender, **kwargs):
        data_fixture.create_workspace(name="Stored while refusing")
        raise AIUsageLimitExceeded("No credits left.")

    ai_request_starting.connect(refuse)
    try:
        with (
            transaction.atomic(),
            patch.object(
                model_type, "get_ai_model", return_value=FunctionModel(respond)
            ),
            pytest.raises(AIUsageLimitExceeded),
        ):
            model_type.prompt(
                MODEL, "Hi", settings_override={"api_key": "x", "models": [MODEL]}
            )
    finally:
        ai_request_starting.disconnect(refuse)
    assert Workspace.objects.filter(name="Stored while refusing").exists()


def test_a_failing_preparing_receiver_is_logged():
    def fail(sender, **kwargs):
        raise RuntimeError("could not prepare")

    ai_usage_preparing.connect(fail)
    try:
        notify_ai_usage_preparing(Workspace(id=1), "other_feature")
    finally:
        ai_usage_preparing.disconnect(fail)


@pytest.mark.django_db
def test_usage_reporting_model_reports_every_request():
    scope = AIUsageScope("openai", MODEL, True, feature="other_feature")
    model = UsageReportingModel(
        FunctionModel(respond, stream_function=respond_streamed), scope
    )

    async def run():
        async with model:
            await Agent(model).run("Hi")
            with ai_usage_context(feature="some_feature", reference_id=3):
                async with Agent(model).run_stream("Streamed") as streamed:
                    await streamed.get_output()

    with Recorder() as recorder:
        async_to_sync(run)()

    assert len(recorder.started) == 2
    assert [scope for scope, _ in recorder.completed] == recorder.started
    # Without a context, the feature of the model is kept.
    assert recorder.started[0] == scope
    # The context at the time of the request is used.
    assert recorder.started[1].feature == "some_feature"
    assert recorder.started[1].reference_id == "3"
    assert recorder.started[1].uses_shared_key is True
    assert recorder.completed[0][1].input_tokens == 120
    assert recorder.completed[1][1].output_tokens > 0


@pytest.mark.django_db
def test_usage_reporting_model_reports_a_stream_that_is_stopped_early():
    async def stream(messages, info):
        yield "Hello"
        yield " world"

    model = UsageReportingModel(
        FunctionModel(stream_function=stream),
        AIUsageScope("openai", MODEL, True),
    )

    async def run():
        async with model:
            async with Agent(model).run_stream("Streamed") as streamed:
                async for _ in streamed.stream_text(delta=True):
                    raise RuntimeError("The consumer failed.")

    with Recorder() as recorder, pytest.raises(RuntimeError):
        async_to_sync(run)()

    ((_, usage),) = recorder.completed
    assert usage.input_tokens > 0


@pytest.mark.django_db
def test_usage_reporting_model_can_be_refused():
    model = UsageReportingModel(
        FunctionModel(respond),
        AIUsageScope("openai", MODEL, True),
    )

    async def run():
        async with model:
            await Agent(model).run("Hi")

    with (
        Recorder(refuse_with=AIUsageLimitExceeded("No credits left.")) as recorder,
        pytest.raises(AIUsageLimitExceeded),
    ):
        async_to_sync(run)()

    assert recorder.completed == []


def test_a_refusal_is_not_logged_as_an_error(caplog):
    model = UsageReportingModel(
        FunctionModel(respond),
        AIUsageScope("openai", MODEL, True),
    )

    async def run():
        async with model:
            await Agent(model).run("Hi")

    with (
        caplog.at_level(logging.ERROR, logger="django.dispatch"),
        Recorder(refuse_with=AIUsageLimitExceeded("No credits left.")),
        pytest.raises(AIUsageLimitExceeded),
    ):
        async_to_sync(run)()

    assert [
        record for record in caplog.records if record.name == "django.dispatch"
    ] == []


def test_usage_reporting_model_does_not_leave_the_loop_without_receivers():
    model = UsageReportingModel(
        FunctionModel(respond),
        AIUsageScope("openai", MODEL, True),
    )

    async def run():
        async with model:
            return (await Agent(model).run("Hi")).output

    with patch("baserow.core.generative_ai.usage.sync_to_async") as sync_to_async:
        assert async_to_sync(run)() == "Hello"

    sync_to_async.assert_not_called()


@pytest.mark.django_db
def test_prompt_reports_the_usage_of_a_run_that_fails_after_a_request(data_fixture):
    model_type = OpenAIGenerativeAIModelType()

    with (
        patch.object(model_type, "get_ai_model", return_value=FunctionModel(respond)),
        # The model never answers in the requested structure.
        patch.object(model_type, "_build_agent", return_value=Agent(output_type=int)),
        Recorder() as recorder,
        pytest.raises(GenerativeAIPromptError),
    ):
        model_type.prompt(
            MODEL, "Hi", settings_override={"api_key": "x", "models": [MODEL]}
        )

    assert len(recorder.completed) > 1
    assert all(usage.input_tokens == 120 for _, usage in recorder.completed)


@pytest.mark.django_db
def test_get_ai_usage_plugin_data_collects_the_data_of_every_plugin():
    calls = []

    class CostPlugin(Plugin):
        type = "cost"

        def get_ai_usage_plugin_data(self, reference_type, reference_ids):
            calls.append((reference_type, reference_ids))
            return {"1": {"credits": 2}}

    class EmptyPlugin(Plugin):
        type = "empty"

    with patch.dict(
        plugin_registry.registry, {"cost": CostPlugin(), "empty": EmptyPlugin()}
    ):
        assert get_ai_usage_plugin_data("job", [1, 2, 1]) == {
            "1": {"cost": {"credits": 2}}
        }
        assert get_ai_usage_plugin_data("job", []) == {}

    # Once for all the ids, as strings.
    assert calls == [("job", ["1", "2"])]


@pytest.mark.django_db
def test_get_ai_usage_plugin_data_leaves_out_a_failing_plugin():
    class BrokenPlugin(Plugin):
        type = "broken"

        def get_ai_usage_plugin_data(self, reference_type, reference_ids):
            raise ValueError("broken")

    class CostPlugin(Plugin):
        type = "cost"

        def get_ai_usage_plugin_data(self, reference_type, reference_ids):
            return {"1": {"credits": 2}}

    with patch.dict(
        plugin_registry.registry, {"broken": BrokenPlugin(), "cost": CostPlugin()}
    ):
        assert get_ai_usage_plugin_data("job", [1]) == {"1": {"cost": {"credits": 2}}}
