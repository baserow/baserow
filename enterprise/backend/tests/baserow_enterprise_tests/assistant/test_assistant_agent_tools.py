from uuid import uuid4

import pytest

from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentApplication, AgentMessage
from baserow_enterprise.assistant.tools.agent.tools import (
    AgentSetup,
    apply_agent_setup,
    get_agent,
    get_agent_test_result,
    list_agent_tools,
)
from baserow_enterprise.assistant.tools.agent.tools import (
    test_agent as start_agent_test,
)
from baserow_enterprise.assistant.tools.shared import ToolInputError
from baserow_enterprise.assistant.types import AgentNavigationType

from .utils import make_test_ctx

ENABLED_MODELS_PATH = (
    "baserow.core.generative_ai.registries.GenerativeAIModelTypeRegistry"
    ".get_enabled_models_per_type"
)


def _ctx(user, workspace):
    return make_test_ctx(user, workspace)


def _apply(ctx, setup, agent_id=None):
    return apply_agent_setup(ctx, AgentSetup(**setup), thought="t", agent_id=agent_id)


@pytest.mark.django_db
def test_an_agent_is_created_with_its_trigger_turned_off(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = data_fixture.create_identity(workspace=workspace)

    result = apply_agent_setup(
        _ctx(user, workspace),
        AgentSetup(
            name="Digest",
            instructions="Summarize open tickets.",
            run_as_identity_id=identity.id,
            allowed_tools=["list_tables"],
            add_triggers=[{"type": "periodic"}],
        ),
        thought="t",
    )

    assert result["changed"] and result["created"]
    setup = result["setup"]
    assert setup["instructions"] == "Summarize open tickets."
    assert setup["allowed_tools"] == ["list_tables"]
    assert [(t["type"], t["enabled"]) for t in setup["triggers"]] == [
        ("periodic", False)
    ]
    assert "doesn't run by itself" in result["next_steps"]


@pytest.mark.django_db
def test_kuma_opens_the_agent_it_changed(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = _ctx(user, workspace)
    navigations = []
    ctx.deps.tool_helpers.navigate_to = navigations.append

    agent_id = _apply(ctx, {"name": "Digest"})["setup"]["agent_id"]

    assert navigations == [
        AgentNavigationType(type="agent", agent_id=agent_id, agent_name="Digest")
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "setup",
    [
        {"add_triggers": [{"type": "periodic", "enabled": True}]},
        {"update_triggers": [{"trigger_id": 1, "enabled": True}]},
        {"allowed_tools": ["create_tables"], "ask_first_tools": []},
    ],
)
def test_kuma_has_no_way_to_turn_a_trigger_on_or_ask_first_off(data_fixture, setup):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = data_fixture.create_identity(workspace=workspace)
    agent = data_fixture.create_agent_application(workspace=workspace)
    trigger = data_fixture.create_agent_trigger(agent=agent, enabled=False)
    setup = {**setup, "run_as_identity_id": identity.id}

    result = _apply(_ctx(user, workspace), setup, agent.id)["setup"]

    trigger.refresh_from_db()
    assert not trigger.enabled
    assert not any(t["enabled"] for t in result["triggers"])
    assert result["ask_first_tools"] == [
        name for name in result["allowed_tools"] if name == "create_tables"
    ]


@pytest.mark.django_db
def test_a_newly_allowed_tool_asks_first_and_the_users_choice_is_kept(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = data_fixture.create_identity(workspace=workspace)
    agent = data_fixture.create_agent_application(workspace=workspace)
    # The user let the Agent create tables without asking.
    AgentHandler().update_configuration(
        agent,
        run_as_subject_type="auth.User",
        run_as_subject_id=identity.id,
        allowed_tools=["create_tables"],
        ask_first_tools=[],
    )

    result = _apply(
        _ctx(user, workspace),
        {"allowed_tools": ["list_tables", "create_tables", "create_fields"]},
        agent.id,
    )["setup"]

    assert result["allowed_tools"] == ["list_tables", "create_tables", "create_fields"]
    assert result["ask_first_tools"] == ["create_fields"]


@pytest.mark.django_db
def test_only_the_user_turns_web_fetch_on(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = _ctx(user, workspace)

    with pytest.raises(ToolInputError, match="open web pages"):
        _apply(ctx, {"name": "Digest", "web_fetch_enabled": True})
    assert not AgentApplication.objects.filter(workspace=workspace).exists()

    agent = data_fixture.create_agent_application(
        workspace=workspace, web_fetch_enabled=True
    )
    result = _apply(ctx, {"web_fetch_enabled": False}, agent.id)

    assert result["setup"]["web_fetch_enabled"] is False
    assert result["revert"] == {
        "setup": {},
        "cannot_undo": [
            "web fetch stays off: the user turns it on in the Agent's Configuration"
        ],
    }


@pytest.mark.django_db
def test_new_instructions_are_refused_while_the_agent_opens_web_pages_alone(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = _agent_that_may_run_alone(data_fixture, workspace, True, None)
    agent.web_fetch_enabled = True
    agent.save()
    ctx = _ctx(user, workspace)

    with pytest.raises(ToolInputError, match="change its instructions"):
        _apply(ctx, {"instructions": "New"}, agent.id)

    result = _apply(ctx, {"instructions": "New", "web_fetch_enabled": False}, agent.id)
    assert result["setup"]["instructions"] == "New"


@pytest.mark.django_db
def test_tools_need_an_identity_to_act_as(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    with pytest.raises(ToolInputError, match="needs an identity"):
        _apply(_ctx(user, workspace), {"name": "Bot", "allowed_tools": ["list_tables"]})
    assert not AgentApplication.objects.filter(workspace=workspace).exists()


@pytest.mark.django_db
def test_testing_an_agent_starts_a_test_conversation(data_fixture, mocker):
    mocker.patch(ENABLED_MODELS_PATH, return_value={"openai": ["gpt-5"]})
    mocker.patch("baserow.core.chat_runs.handler.ChatRunHandler.start_run")
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = data_fixture.create_agent_application(
        workspace=workspace,
        instructions="Say hi.",
        provider_type="openai",
        model_identifier="gpt-5",
    )

    result = start_agent_test(_ctx(user, workspace), agent.id, "Hi", thought="t")

    conversation = agent.conversations.get(uuid=result["conversation_uuid"])
    assert (conversation.is_test, conversation.title) == (True, "Test: Hi")


@pytest.mark.django_db
def test_a_test_conversation_asks_first_for_mcp_tools_that_change_data(
    data_fixture,
):
    from baserow.contrib.integrations.mcp.models import MCPServerTool

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = _agent_that_may_run_alone(data_fixture, workspace, False, None)
    agent.provider_type, agent.model_identifier = "openai", "m"
    agent.save()
    server = data_fixture.create_mcp_server_integration(application=agent)
    for name, changes_data in (("send", True), ("read", False)):
        MCPServerTool.objects.create(
            integration=server,
            name=name,
            definition_hash=name,
            enabled=True,
            changes_data=changes_data,
            ask_first=False,
        )
    asks = {}
    for is_test in (False, True):
        conversation = data_fixture.create_agent_conversation(
            user=user, agent=agent, is_test=is_test
        )
        data_fixture.create_agent_message(conversation=conversation, content="Hi")
        reply = AgentMessage.objects.create(
            conversation=conversation,
            uuid=uuid4(),
            role=AgentMessage.Role.ASSISTANT,
            content="",
        )
        request = AgentHandler().get_reply_request(reply)
        asks[is_test] = {
            tool.name: tool.ask_first
            for server in request.mcp_servers
            for tool in server.tools
        }

    assert asks[False] == {"send": False, "read": False}
    assert asks[True] == {"send": True, "read": False}


@pytest.mark.django_db
def test_kuma_turns_a_trigger_off(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = _agent_that_may_run_alone(data_fixture, workspace, True)
    trigger = agent.triggers.get()

    result = _apply(
        _ctx(user, workspace), {"turn_off_triggers": [trigger.id]}, agent.id
    )

    assert [t["enabled"] for t in result["setup"]["triggers"]] == [False]
    assert result["revert"] == {
        "setup": {},
        "cannot_undo": [
            f'the trigger "{trigger.name}" stays turned off: the user turns it on '
            "in the Agent's Configuration"
        ],
    }


@pytest.mark.django_db
def test_a_test_conversation_asks_first_for_every_tool_that_changes_data(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = data_fixture.create_identity(workspace=workspace)
    agent = data_fixture.create_agent_application(
        workspace=workspace, provider_type="openai", model_identifier="m"
    )
    AgentHandler().update_configuration(
        agent,
        run_as_subject_type="auth.User",
        run_as_subject_id=identity.id,
        allowed_tools=["list_tables", "create_tables"],
        ask_first_tools=[],
    )
    requests = {}
    for is_test in (False, True):
        conversation = data_fixture.create_agent_conversation(
            user=user, agent=agent, is_test=is_test
        )
        data_fixture.create_agent_message(conversation=conversation, content="Hi")
        reply = AgentMessage.objects.create(
            conversation=conversation,
            uuid=uuid4(),
            role=AgentMessage.Role.ASSISTANT,
            content="",
        )
        requests[is_test] = AgentHandler().get_reply_request(reply)

    assert requests[False].ask_first_tool_names == []
    assert requests[True].ask_first_tool_names == ["create_tables"]


@pytest.mark.django_db
def test_editing_an_agent_renames_it(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = data_fixture.create_agent_application(workspace=workspace, name="Old")

    result = apply_agent_setup(
        _ctx(user, workspace), AgentSetup(name="New"), thought="t", agent_id=agent.id
    )

    agent.refresh_from_db()
    assert agent.name == "New"
    assert result["changed"] and result["setup"]["name"] == "New"
    assert result["previous_setup"]["name"] == "Old"

    unchanged = apply_agent_setup(
        _ctx(user, workspace), AgentSetup(name="New"), thought="t", agent_id=agent.id
    )
    assert not unchanged["changed"]


@pytest.mark.django_db
def test_testing_an_agent_that_isnt_ready_returns_an_error_to_kuma(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = data_fixture.create_agent_application(workspace=workspace)

    with pytest.raises(ToolInputError, match="isn't ready"):
        start_agent_test(_ctx(user, workspace), agent.id, "Hi", thought="t")


@pytest.mark.django_db
def test_a_too_long_agent_name_returns_an_error_to_kuma(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    with pytest.raises(ToolInputError, match="at most 160"):
        apply_agent_setup(
            _ctx(user, workspace), AgentSetup(name="a" * 161), thought="t"
        )


@pytest.mark.django_db
def test_an_identity_role_that_doesnt_exist_returns_an_error_to_kuma(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    setup = {"name": "Bot", "new_identity": {"name": "Bot", "role": "NOPE"}}

    with pytest.raises(ToolInputError, match="role doesn't exist"):
        _apply(_ctx(user, workspace), setup)
    assert not AgentApplication.objects.filter(workspace=workspace).exists()


@pytest.mark.django_db
def test_a_refused_trigger_returns_an_error_to_kuma(data_fixture, settings):
    settings.INTEGRATIONS_PERIODIC_MINUTE_MIN = 5
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = _ctx(user, workspace)

    setup = AgentSetup(
        name="Digest",
        add_triggers=[
            {"type": "periodic", "schedule": {"interval": "MINUTE", "minute": 1}}
        ],
    )
    with pytest.raises(ToolInputError, match="minute"):
        apply_agent_setup(ctx, setup, thought="t")
    assert not AgentApplication.objects.filter(workspace=workspace).exists()


@pytest.mark.django_db
def test_a_schedule_runs_in_the_users_timezone(data_fixture):
    user = data_fixture.create_user()
    user.profile.timezone = "Europe/Amsterdam"
    user.profile.save()
    workspace = data_fixture.create_workspace(user=user)
    schedule = {"interval": "WEEK", "day_of_week": 0, "hour": 8}

    result = _apply(
        _ctx(user, workspace),
        {
            "name": "Digest",
            "add_triggers": [{"type": "periodic", "schedule": schedule}],
        },
    )

    [trigger] = result["setup"]["triggers"]
    assert not trigger["enabled"]
    assert trigger["schedule"] == {
        "interval": "WEEK",
        "hour": 8,
        "minute": 0,
        "day_of_week": 0,
        "day_of_month": 1,
        "timezone": "Europe/Amsterdam",
    }


@pytest.mark.django_db
def test_kuma_only_sets_a_model_that_is_enabled_for_agents(data_fixture, mocker):
    mocker.patch(ENABLED_MODELS_PATH, return_value={"openai": ["gpt-5"]})
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = data_fixture.create_agent_application(workspace=workspace)
    ctx = _ctx(user, workspace)

    with pytest.raises(ToolInputError, match="isn't enabled") as refused:
        apply_agent_setup(
            ctx,
            AgentSetup(provider_type="", model_identifier="anthropic/claude-haiku-4-5"),
            thought="t",
            agent_id=agent.id,
        )
    assert "gpt-5" in refused.value.hint
    agent.refresh_from_db()
    assert not agent.provider_type and not agent.model_identifier

    assert list_agent_tools(ctx, thought="t")["models"] == [
        {"provider_type": "openai", "model_identifier": "gpt-5"}
    ]

    result = apply_agent_setup(
        ctx,
        AgentSetup(
            instructions="Say hi.", provider_type="openai", model_identifier="gpt-5"
        ),
        thought="t",
        agent_id=agent.id,
    )
    assert result["setup"]["readiness"] == "ready"
    assert "Offer a test" in result["next_steps"]


@pytest.mark.django_db
def test_kuma_says_a_new_agent_isnt_ready_when_no_model_is_enabled(
    data_fixture, mocker
):
    mocker.patch(ENABLED_MODELS_PATH, return_value={})
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    result = apply_agent_setup(
        _ctx(user, workspace),
        AgentSetup(name="Digest", instructions="Summarize."),
        thought="t",
    )

    assert "not ready" in result["next_steps"]
    assert "Offer a test" not in result["next_steps"]
    assert result["setup"]["readiness"] != "ready"
    assert "model_identifier" in result["setup"]["readiness_errors"]


@pytest.mark.django_db
def test_reverting_a_change_puts_back_what_it_can_and_says_what_stays(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = _ctx(user, workspace)
    agent_id = apply_agent_setup(
        ctx, AgentSetup(name="Digest", instructions="Old"), thought="t"
    )["setup"]["agent_id"]

    change = apply_agent_setup(
        ctx,
        AgentSetup(
            name="Weekly digest",
            instructions="New",
            add_triggers=[{"type": "periodic"}],
        ),
        thought="t",
        agent_id=agent_id,
    )
    revert = change["revert"]
    reverted = apply_agent_setup(
        ctx, AgentSetup(**revert["setup"]), thought="t", agent_id=agent_id
    )["setup"]

    assert (reverted["name"], reverted["instructions"]) == ("Digest", "Old")
    [trigger] = reverted["triggers"]
    assert not trigger["enabled"]
    assert revert["cannot_undo"] == [
        f'the trigger "{trigger["name"]}" stays, turned off'
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "schedule,error",
    [
        ({"interval": "MINUTE", "minute": 0}, "must be 1 or more"),
        ({"interval": "DAY", "timezone": "PST"}, "not a timezone"),
    ],
)
def test_a_schedule_that_cant_be_saved_is_refused(data_fixture, schedule, error):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    setup = AgentSetup(
        name="Digest",
        add_triggers=[{"type": "periodic", "schedule": schedule}],
    )

    with pytest.raises(ToolInputError, match=error):
        apply_agent_setup(_ctx(user, workspace), setup, thought="t")


@pytest.mark.django_db
def test_waiting_for_a_test_reply_stops_when_kuma_is_cancelled(data_fixture, mocker):
    import asyncio
    from types import SimpleNamespace

    from baserow.contrib.agent.models import AgentReplyStatus

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = data_fixture.create_agent_application(workspace=workspace)
    conversation = data_fixture.create_agent_conversation(user=user, agent=agent)
    AgentMessage.objects.create(
        conversation=conversation,
        uuid=uuid4(),
        role=AgentMessage.Role.ASSISTANT,
        content="",
        status=AgentReplyStatus.QUEUED,
    )
    ctx = _ctx(user, workspace)
    clock = [0.0]

    def sleep(seconds):
        # The user stops Kuma during the first wait.
        ctx.deps.tool_helpers._cancel_event.set()
        clock[0] += seconds

    mocker.patch(
        "baserow_enterprise.assistant.tools.agent.tools.time",
        SimpleNamespace(monotonic=lambda: clock[0], sleep=sleep),
    )

    with pytest.raises(asyncio.CancelledError):
        get_agent_test_result(ctx, agent.id, conversation.uuid, thought="t")
    assert clock[0] == 1


def _agent_that_may_run_alone(data_fixture, workspace, trigger_on, changes_with="tool"):
    """
    An Agent with a trigger, and a way to change data without asking first:
    a built-in tool, an action, an MCP tool, or none.
    """

    from baserow.contrib.integrations.mcp.models import MCPServerTool

    identity = data_fixture.create_identity(workspace=workspace)
    agent = data_fixture.create_agent_application(
        workspace=workspace, instructions="Old"
    )
    AgentHandler().update_configuration(
        agent,
        run_as_subject_type="auth.User",
        run_as_subject_id=identity.id,
        allowed_tools=["list_tables", "create_tables"],
        ask_first_tools=[] if changes_with == "tool" else ["create_tables"],
    )
    data_fixture.create_agent_trigger(agent=agent, enabled=trigger_on)
    if changes_with == "action":
        data_fixture.create_agent_action(agent=agent, enabled=True)
    if changes_with == "mcp":
        server = data_fixture.create_mcp_server_integration(application=agent)
        MCPServerTool.objects.create(
            integration=server,
            name="send",
            definition_hash="h",
            enabled=True,
            changes_data=True,
            ask_first=False,
        )
    return agent


@pytest.mark.django_db
@pytest.mark.parametrize("changes_with", ["tool", "action", "mcp"])
def test_new_instructions_are_refused_while_the_agent_changes_data_alone(
    data_fixture, changes_with
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = _agent_that_may_run_alone(data_fixture, workspace, True, changes_with)

    with pytest.raises(ToolInputError, match="change its instructions") as refused:
        _apply(_ctx(user, workspace), {"instructions": "New"}, agent.id)

    assert "turn_off_triggers" in refused.value.hint
    agent.refresh_from_db()
    assert agent.instructions == "Old"


@pytest.mark.django_db
@pytest.mark.parametrize("trigger_on,changes_with", [(False, "tool"), (True, None)])
def test_new_instructions_apply_when_the_agent_cant_change_data_alone(
    data_fixture, trigger_on, changes_with
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = _agent_that_may_run_alone(data_fixture, workspace, trigger_on, changes_with)

    result = _apply(_ctx(user, workspace), {"instructions": "New"}, agent.id)

    assert result["setup"]["instructions"] == "New"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "change,refusal",
    [
        ({"new_identity": {"name": "Bot", "role": "MEMBER"}}, "new identity"),
        ({"run_as_identity_id": "other"}, "run it as the identity"),
    ],
)
def test_identity_changes_wait_until_the_triggers_are_off(
    data_fixture, change, refusal
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = _agent_that_may_run_alone(data_fixture, workspace, True, None)
    if change.get("run_as_identity_id"):
        other = data_fixture.create_identity(workspace=workspace)
        change = {"run_as_identity_id": other.id}
    ctx = _ctx(user, workspace)
    before = get_agent(ctx, agent.id, thought="t")

    with pytest.raises(ToolInputError, match=refusal):
        _apply(ctx, change, agent.id)
    assert get_agent(ctx, agent.id, thought="t") == before

    trigger = agent.triggers.get()
    result = _apply(ctx, {**change, "turn_off_triggers": [trigger.id]}, agent.id)
    assert result["changed"]
    assert [t["enabled"] for t in result["setup"]["triggers"]] == [False]
