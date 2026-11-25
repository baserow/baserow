from uuid import uuid4

import pytest

from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentApplication, AgentMessage
from baserow_enterprise.assistant.tools.agent.tools import (
    apply_agent_setup,
    get_agent,
    get_agent_test_result,
    list_agent_tools,
    list_agents,
)
from baserow_enterprise.assistant.tools.agent.tools import (
    test_agent as start_agent_test,
)
from baserow_enterprise.assistant.tools.agent.types import AgentSetup
from baserow_enterprise.assistant.tools.shared import ToolInputError
from baserow_enterprise.assistant.types import AgentNavigationType

from .utils import make_test_ctx

ROW_READS = ["list_tables", "get_table_schema", "list_table_rows"]
ENABLED_MODELS_PATH = (
    "baserow.core.generative_ai.registries.GenerativeAIModelTypeRegistry"
    ".get_enabled_models_per_type"
)


def _ctx(user, workspace):
    return make_test_ctx(user, workspace)


def _workspace_with_roles(data_fixture, admin, builder, editor):
    from baserow_enterprise.role.handler import RoleAssignmentHandler
    from baserow_enterprise.role.models import Role

    workspace = data_fixture.create_workspace(user=admin, members=[builder, editor])
    for user, uid in ((builder, "BUILDER"), (editor, "EDITOR")):
        RoleAssignmentHandler().assign_role(
            user, workspace, role=Role.objects.get(uid=uid)
        )
    return workspace


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
            grant_tools=["list_tables"],
            add_triggers=[{"type": "periodic", "schedule": {"interval": "DAY"}}],
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
        {
            "add_triggers": [
                {
                    **{"type": "periodic", "schedule": {"interval": "DAY"}},
                    "enabled": True,
                }
            ]
        },
        {"update_triggers": [{"trigger_id": 1, "enabled": True}]},
        {"grant_tools": ["list_databases", "create_tables"], "ask_first_tools": []},
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
        allowed_tools=["list_databases", "create_tables"],
        ask_first_tools=[],
    )

    result = _apply(
        _ctx(user, workspace),
        {"grant_tools": ["list_tables", "get_table_schema", "create_fields"]},
        agent.id,
    )["setup"]

    assert set(result["allowed_tools"]) == {
        "list_databases",
        "list_tables",
        "get_table_schema",
        "create_tables",
        "create_fields",
    }
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
        _apply(_ctx(user, workspace), {"name": "Bot", "grant_tools": ["list_tables"]})
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
def test_a_test_conversation_asks_first_for_every_mcp_tool(
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
            sender=user,
        )
        request = AgentHandler().get_reply_request(reply)
        asks[is_test] = {
            tool.name: tool.ask_first
            for server in request.mcp_servers
            for tool in server.tools
        }

    assert asks[False] == {"send": False, "read": False}
    # A server says itself which of its tools only read, so a test trusts none.
    assert asks[True] == {"send": True, "read": True}


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
            sender=user,
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
    schedule = {"interval": "WEEK", "day_of_week": "MONDAY", "hour": 8}

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
        "day_of_week": "MONDAY",
        "day_of_month": None,
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
    assert "offer a test" in result["next_steps"]


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
    assert "offer a test" not in result["next_steps"]
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
            add_triggers=[{"type": "periodic", "schedule": {"interval": "DAY"}}],
            add_actions=[{"type": "http_request", "name": "notify"}],
        ),
        thought="t",
        agent_id=agent_id,
    )
    assert [a["enabled"] for a in change["setup"]["actions"]] == [False]
    revert = change["revert"]
    reverted = apply_agent_setup(
        ctx, AgentSetup(**revert["setup"]), thought="t", agent_id=agent_id
    )["setup"]

    assert (reverted["name"], reverted["instructions"]) == ("Digest", "Old")
    assert reverted["triggers"] == reverted["actions"] == []
    assert revert["cannot_undo"] == []


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
        ({"new_identity": {"name": "Bot"}}, "new identity"),
        ({"run_as_identity_id": "other"}, "run it as another identity"),
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


@pytest.mark.django_db
def test_tools_are_granted_and_revoked_one_by_one(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = data_fixture.create_identity(workspace=workspace)
    agent = data_fixture.create_agent_application(workspace=workspace)
    AgentHandler().update_configuration(
        agent,
        run_as_subject_type="auth.User",
        run_as_subject_id=identity.id,
        allowed_tools=[*ROW_READS, "list_databases", "create_tables", "update_rows"],
        ask_first_tools=["update_rows"],
    )
    ctx = _ctx(user, workspace)

    result = _apply(
        ctx,
        {"grant_tools": ["delete_rows"], "revoke_tools": ["create_tables"]},
        agent.id,
    )

    # Tools the change doesn't name keep what the user set.
    assert set(result["setup"]["allowed_tools"]) == {
        *ROW_READS,
        "list_databases",
        "update_rows",
        "delete_rows",
    }
    assert set(result["setup"]["ask_first_tools"]) == {"update_rows", "delete_rows"}
    assert result["revert"]["setup"] == {
        "revoke_tools": ["delete_rows"],
        "grant_tools": ["create_tables"],
    }

    with pytest.raises(ToolInputError, match="list_rows"):
        _apply(ctx, {"grant_tools": ["list_rows"]}, agent.id)
    with pytest.raises(ToolInputError, match="delete_rows requires list_table_rows"):
        _apply(ctx, {"revoke_tools": ["list_table_rows"]}, agent.id)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tools,needed",
    [
        (["list_tables"], "VIEWER"),
        ([*ROW_READS, "update_rows"], "EDITOR"),
        ([*ROW_READS, "update_rows", "create_fields"], "BUILDER"),
        # Reading comments needs the same role as writing them.
        ([*ROW_READS, "list_row_comments"], "COMMENTER"),
        ([*ROW_READS, "create_row_comments"], "COMMENTER"),
    ],
)
def test_a_new_identity_gets_the_lowest_role_that_covers_the_tools(
    enable_enterprise, synced_roles, data_fixture, tools, needed
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    result = _apply(
        _ctx(user, workspace),
        {"name": "Bot", "new_identity": {"name": "Bot"}, "grant_tools": tools},
    )

    assert result["setup"]["run_as"]["role"] == needed


@pytest.mark.django_db
def test_without_the_roles_licence_a_new_identity_is_a_member(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    result = _apply(
        _ctx(user, workspace),
        {
            "name": "Bot",
            "new_identity": {"name": "Bot"},
            "grant_tools": ["list_tables"],
        },
    )

    assert result["setup"]["run_as"]["role"] == "MEMBER"


@pytest.mark.django_db
def test_kuma_says_when_the_identitys_role_is_below_the_tools(
    enable_enterprise, synced_roles, data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = _ctx(user, workspace)
    agent_id = _apply(
        ctx,
        {
            "name": "Bot",
            "new_identity": {"name": "Bot"},
            "grant_tools": ["list_tables"],
        },
    )["setup"]["agent_id"]

    result = _apply(ctx, {"grant_tools": [*ROW_READS, "update_rows"]}, agent_id)

    assert "has the VIEWER role" in result["next_steps"]
    assert "need EDITOR" in result["next_steps"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name", ["Reset at https://evil.example/login", "a" * 151, "", "   "]
)
def test_an_identity_name_follows_the_identities_api(name):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AgentSetup(name="Bot", new_identity={"name": name})


def test_the_setup_refuses_what_the_agent_api_refuses():
    from pydantic import ValidationError

    for setup in (
        {"instructions": "a" * 100_001},
        {"add_triggers": [{"type": "local_baserow_rows_created"}]},
        {"add_triggers": [{"type": "periodic", "schedule": {"interval": "WEEK"}}]},
        {"add_actions": [{"type": "http_request", "name": "notify sales!"}]},
        {
            "add_actions": [
                {"type": "http_request", "name": "notify", "description": "a" * 10_001}
            ]
        },
        # Sent in both, a tool that runs unasked would look taken away to the
        # checks and stay as it is.
        {"grant_tools": ["update_rows"], "revoke_tools": ["update_rows"]},
        {
            "remove_triggers": [1],
            "change_schedules": [{"trigger_id": 1, "schedule": {"interval": "DAY"}}],
        },
    ):
        with pytest.raises(ValidationError):
            AgentSetup(**setup)


@pytest.mark.django_db
def test_list_agent_tools_says_which_identities_the_user_can_use(
    enable_enterprise, synced_roles, data_fixture
):
    admin = data_fixture.create_user()
    builder = data_fixture.create_user()
    editor = data_fixture.create_user()
    workspace = _workspace_with_roles(data_fixture, admin, builder, editor)
    identity = data_fixture.create_identity(workspace=workspace, name="Bot")

    def identities(user):
        return list_agent_tools(_ctx(user, workspace), thought="t")["identities"]

    assert identities(admin)["can_create"] is True
    assert identities(builder)["can_create"] is False
    assert [i["identity_id"] for i in identities(builder)["selectable"]] == [
        identity.id
    ]
    with pytest.raises(ToolInputError, match="Builder role"):
        identities(editor)


@pytest.mark.django_db
def test_a_builder_is_told_to_pick_an_identity_and_an_editor_which_role_they_need(
    enable_enterprise, synced_roles, data_fixture
):
    admin = data_fixture.create_user()
    builder = data_fixture.create_user()
    editor = data_fixture.create_user()
    workspace = _workspace_with_roles(data_fixture, admin, builder, editor)
    identity = data_fixture.create_identity(workspace=workspace, name="Bot")
    setup = {"name": "Digest", "new_identity": {"name": "Digest"}}

    with pytest.raises(ToolInputError, match="Only a workspace admin") as refused:
        _apply(_ctx(builder, workspace), setup)
    assert str(identity.id) in refused.value.hint
    assert not AgentApplication.objects.filter(workspace=workspace).exists()

    built = _apply(
        _ctx(builder, workspace),
        {"name": "Digest", "run_as_identity_id": identity.id},
    )
    assert built["setup"]["run_as"]["identity_id"] == identity.id

    with pytest.raises(ToolInputError, match="Builder role"):
        _apply(_ctx(editor, workspace), {"name": "Mine"})
    assert AgentApplication.objects.filter(workspace=workspace).count() == 1


@pytest.mark.django_db
def test_an_identity_turns_on_the_tools_an_imported_agent_waits_with(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = data_fixture.create_identity(workspace=workspace)
    agent = data_fixture.create_agent_application(workspace=workspace)
    agent.pending_tool_choices = {
        "allowed_tools": [*ROW_READS, "list_databases", "update_rows"],
        "ask_first_tools": ["list_tables"],
    }
    agent.save()

    result = _apply(
        _ctx(user, workspace), {"run_as_identity_id": identity.id}, agent.id
    )

    # The template's own ask first is kept. It let update_rows run unasked;
    # through Kuma it asks first.
    assert result["tools_turned_on"] == [
        {"name": "list_databases", "asks_first": False},
        {"name": "list_tables", "asks_first": True},
        {"name": "get_table_schema", "asks_first": False},
        {"name": "list_table_rows", "asks_first": False},
        {"name": "update_rows", "asks_first": True},
    ]
    assert "tools_turned_on" in result["next_steps"]


@pytest.mark.django_db
def test_a_new_schedule_keeps_the_trigger_and_turns_it_off(data_fixture):
    from baserow.contrib.agent.models import AgentTrigger
    from baserow.core.formula.literals import wrap_static_string

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = _ctx(user, workspace)
    weekly = {
        "type": "periodic",
        "schedule": {"interval": "WEEK", "day_of_week": "MONDAY", "hour": 9},
    }
    created = _apply(ctx, {"name": "Digest", "add_triggers": [weekly]})["setup"]
    [old] = created["triggers"]
    message = wrap_static_string("Summarise the leads")
    AgentTrigger.objects.filter(id=old["trigger_id"]).update(
        name="Morning digest", message=message, enabled=True
    )

    change = {"trigger_id": old["trigger_id"], "schedule": {"interval": "DAY"}}
    result = _apply(ctx, {"change_schedules": [change]}, created["agent_id"])

    [trigger] = result["setup"]["triggers"]
    assert trigger["trigger_id"] == old["trigger_id"]
    assert (trigger["name"], trigger["enabled"]) == ("Morning digest", False)
    # The Monday of the old schedule isn't shown for a daily one.
    assert trigger["schedule"]["interval"] == "DAY"
    assert trigger["schedule"]["day_of_week"] is None
    saved = AgentTrigger.objects.get(id=old["trigger_id"]).message
    assert saved["formula"] == message
    # Putting the old schedule back is part of the revert.
    assert result["revert"]["setup"]["change_schedules"] == [
        {"trigger_id": old["trigger_id"], "schedule": old["schedule"]}
    ]


@pytest.mark.django_db
def test_only_a_periodic_trigger_gets_a_new_schedule(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = data_fixture.create_agent_application(workspace=workspace)
    trigger = data_fixture.create_agent_trigger(agent=agent, enabled=False)
    change = {"trigger_id": trigger.id + 1, "schedule": {"interval": "DAY"}}

    with pytest.raises(ToolInputError, match="not a periodic trigger"):
        _apply(_ctx(user, workspace), {"change_schedules": [change]}, agent.id)


@pytest.mark.django_db
def test_listing_agents_leaves_out_their_instructions(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = data_fixture.create_agent_application(
        workspace=workspace, name="Digest", instructions="Summarize. " * 500
    )

    [listed] = list_agents(_ctx(user, workspace), thought="t")["agents"]

    assert (listed["agent_id"], listed["name"]) == (agent.id, "Digest")
    assert "instructions" not in listed


@pytest.mark.django_db
def test_an_agent_id_that_isnt_real_never_creates_an_agent(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    with pytest.raises(ToolInputError, match="does not exist"):
        _apply(_ctx(user, workspace), {"name": "Digest"}, agent_id=0)
    assert not AgentApplication.objects.filter(workspace=workspace).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status,pending,says",
    [
        ("running", False, "still replying"),
        ("completed", True, "not in this chat"),
        ("completed", False, "Don't answer it yourself"),
        ("failed", False, "didn't complete"),
    ],
)
def test_a_test_result_says_what_to_tell_the_user(data_fixture, status, pending, says):
    from baserow.contrib.agent.models import AgentToolApproval

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = data_fixture.create_agent_application(workspace=workspace)
    conversation = data_fixture.create_agent_conversation(
        user=user, agent=agent, is_test=True, title="Test: Hi"
    )
    reply = AgentMessage.objects.create(
        conversation=conversation,
        uuid=uuid4(),
        role=AgentMessage.Role.ASSISTANT,
        content="Which ticket?",
        status=status,
    )
    if pending:
        AgentToolApproval.objects.create(
            reply=reply,
            tool_call_id="call",
            step_id="step",
            pause=1,
            tool_name="update_rows",
        )
    ctx = _ctx(user, workspace)
    if status == "running":
        ctx.deps.tool_helpers.raise_if_cancelled = lambda: None
        import baserow_enterprise.assistant.tools.agent.tools as agent_tools

        agent_tools.TEST_RESULT_WAIT_SECONDS, wait = (
            0,
            agent_tools.TEST_RESULT_WAIT_SECONDS,
        )
    try:
        result = get_agent_test_result(ctx, agent.id, conversation.uuid, thought="t")
    finally:
        if status == "running":
            agent_tools.TEST_RESULT_WAIT_SECONDS = wait

    assert says in result["next_steps"]
    assert 'conversation "Test: Hi"' in result["next_steps"]


@pytest.mark.django_db
def test_a_new_identity_covers_the_tools_the_agent_already_has(
    enable_enterprise, synced_roles, data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = _ctx(user, workspace)
    created = _apply(
        ctx,
        {
            "name": "Bot",
            "new_identity": {"name": "Bot"},
            "grant_tools": [*ROW_READS, "update_rows"],
        },
    )["setup"]

    result = _apply(ctx, {"new_identity": {"name": "Its own"}}, created["agent_id"])

    assert result["setup"]["run_as"]["name"] == "Its own"
    assert result["setup"]["run_as"]["role"] == "EDITOR"


@pytest.mark.django_db
def test_web_search_isnt_turned_on_for_an_agent_that_changes_data_alone(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    alone = _agent_that_may_run_alone(data_fixture, workspace, True)
    asking = _agent_that_may_run_alone(data_fixture, workspace, True, None)
    ctx = _ctx(user, workspace)

    with pytest.raises(ToolInputError, match="search the web"):
        _apply(ctx, {"web_search_enabled": True}, alone.id)

    result = _apply(ctx, {"web_search_enabled": True}, asking.id)
    assert result["setup"]["web_search_enabled"] is True


def test_an_agent_acts_as_one_identity():
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="not both"):
        AgentSetup(run_as_identity_id=1, new_identity={"name": "Bot"})


@pytest.mark.django_db
def test_a_second_agent_isnt_built_under_a_name_that_exists(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = data_fixture.create_agent_application(workspace=workspace, name="Digest")

    # The name is compared as it is saved: trimmed.
    with pytest.raises(ToolInputError, match="already exists") as refused:
        _apply(_ctx(user, workspace), {"name": " digest "})

    assert str(agent.id) in str(refused.value)
    assert AgentApplication.objects.filter(workspace=workspace).count() == 1


def test_every_agent_tool_says_which_role_it_needs():
    from baserow.contrib.agent.registries import agent_tool_type_registry
    from baserow_enterprise.assistant.tools.agent.tools import ROLE_FOR_NEEDS

    for tool_type in agent_tool_type_registry.get_all():
        assert tool_type.needs in ROLE_FOR_NEEDS, tool_type.type


@pytest.mark.django_db
def test_a_model_is_checked_as_it_is_saved(data_fixture, mocker):
    mocker.patch(ENABLED_MODELS_PATH, return_value={"openai": ["gpt-5"]})
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = data_fixture.create_agent_application(
        workspace=workspace,
        instructions="Say hi.",
        provider_type="openai",
        model_identifier="gpt-5",
    )

    # An empty model used to pass as the current one and was then saved empty.
    for cleared in (
        {"model_identifier": ""},
        {"provider_type": "", "model_identifier": ""},
    ):
        with pytest.raises(ToolInputError, match="isn't enabled"):
            _apply(_ctx(user, workspace), cleared, agent.id)

    agent.refresh_from_db()
    assert agent.model_identifier == "gpt-5"


@pytest.mark.django_db
def test_instructions_that_were_cut_in_kumas_memory_arent_saved(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = data_fixture.create_agent_application(
        workspace=workspace, instructions="a" * 400
    )

    with pytest.raises(ToolInputError, match="cut short"):
        _apply(_ctx(user, workspace), {"instructions": "a" * 157 + "..."}, agent.id)

    agent.refresh_from_db()
    assert agent.instructions == "a" * 400


@pytest.mark.django_db
def test_kuma_says_what_starts_the_agent_after_the_change(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = _ctx(user, workspace)
    running = _agent_that_may_run_alone(data_fixture, workspace, True, None)

    result = _apply(ctx, {"name": "Renamed"}, running.id)
    assert "so the Agent runs by itself" in result["next_steps"]
    assert "doesn't run by itself" not in result["next_steps"]

    plain = _apply(ctx, {"name": "Plain"})
    assert "has no trigger" in plain["next_steps"]


@pytest.mark.django_db
def test_kuma_says_when_the_agents_identity_is_gone(data_fixture):
    from baserow.core.identities.handler import IdentityHandler

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = _agent_that_may_run_alone(data_fixture, workspace, False, None)
    run_as = get_agent(_ctx(user, workspace), agent.id, thought="t")["run_as"]
    assert run_as["available"] is True
    IdentityHandler().get_queryset(workspace).filter(id=run_as["identity_id"]).delete()

    result = _apply(_ctx(user, workspace), {"name": "Renamed"}, agent.id)

    assert result["setup"]["run_as"]["available"] is False
    assert "trashed or gone" in result["next_steps"]


@pytest.mark.django_db
def test_without_identities_turned_on_kuma_creates_none(data_fixture, settings):
    settings.FEATURE_FLAGS = ["agent-builder"]
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = _ctx(user, workspace)

    identities = list_agent_tools(ctx, thought="t")["identities"]
    assert identities["can_create"] is False
    assert "aren't turned on" in identities["cannot_create_because"]

    with pytest.raises(ToolInputError, match="aren't turned on"):
        _apply(ctx, {"name": "Bot", "new_identity": {"name": "Bot"}})
    assert not AgentApplication.objects.filter(workspace=workspace).exists()


@pytest.mark.django_db
def test_no_identity_to_pick_isnt_told_as_a_missing_role(data_fixture):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)

    with pytest.raises(ToolInputError, match="does not exist"):
        _apply(_ctx(admin, workspace), {"name": "Bot", "run_as_identity_id": 999999})
    assert not AgentApplication.objects.filter(workspace=workspace).exists()


@pytest.mark.django_db
def test_a_builder_without_identities_is_sent_to_an_admin(
    enable_enterprise, synced_roles, data_fixture
):
    admin = data_fixture.create_user()
    builder = data_fixture.create_user()
    editor = data_fixture.create_user()
    workspace = _workspace_with_roles(data_fixture, admin, builder, editor)

    with pytest.raises(ToolInputError, match="no identity to choose") as refused:
        _apply(
            _ctx(builder, workspace),
            {"name": "Bot", "new_identity": {"name": "Bot"}},
        )
    assert "Only a workspace admin can create an identity" in str(refused.value)


@pytest.mark.django_db
def test_a_test_result_names_the_tool_of_each_step_and_its_error(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = data_fixture.create_agent_application(workspace=workspace)
    conversation = data_fixture.create_agent_conversation(
        user=user, agent=agent, is_test=True
    )
    AgentMessage.objects.create(
        conversation=conversation,
        uuid=uuid4(),
        role=AgentMessage.Role.ASSISTANT,
        content="",
        status="failed",
        steps=[
            {
                "id": "1",
                "tool": "update_rows",
                "status": "failed",
                "error_code": "permission_denied",
                "error_message": "The identity can't change this table.",
                "input": {"table": "Leads"},
                "facts": {},
            }
        ],
    )

    result = get_agent_test_result(
        _ctx(user, workspace), agent.id, conversation.uuid, thought="t"
    )

    assert result["steps"] == [
        {
            "tool": "update_rows",
            "status": "failed",
            "input": {"table": "Leads"},
            "error_code": "permission_denied",
            "error_message": "The identity can't change this table.",
        }
    ]


@pytest.mark.parametrize(
    "prompt,title",
    [
        ("Hi", "Test: Hi"),
        ("Test the triage with a lead", "Test the triage with a lead"),
        ("Testimonials summary", "Test: Testimonials summary"),
    ],
)
def test_a_test_title_says_test_once(prompt, title):
    from baserow_enterprise.assistant.tools.agent.tools import _test_title

    assert _test_title(prompt) == title


@pytest.mark.django_db
def test_a_change_saved_while_kuma_waits_for_the_agent_is_kept(data_fixture, mocker):
    from baserow.contrib.agent.service import AgentService

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = data_fixture.create_agent_application(
        workspace=workspace, instructions="Old", web_fetch_enabled=True
    )
    lock = AgentService.get_authorized_agent

    def saved_in_the_configuration_first(self, *args, **kwargs):
        if kwargs.get("for_update"):
            AgentApplication.objects.filter(id=agent.id).update(
                instructions="New", web_fetch_enabled=False
            )
        return lock(self, *args, **kwargs)

    mocker.patch.object(
        AgentService,
        "get_authorized_agent",
        autospec=True,
        side_effect=saved_in_the_configuration_first,
    )

    _apply(_ctx(user, workspace), {"name": "Renamed"}, agent.id)

    agent.refresh_from_db()
    assert (agent.name, agent.instructions) == ("Renamed", "New")
    assert agent.web_fetch_enabled is False
