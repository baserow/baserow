from uuid import uuid4

from django.urls import reverse

import pytest

from baserow.core.handler import CoreHandler

from .utils import agent_url, new_conversation


@pytest.fixture
def template_agent(data_fixture, configured_agent):
    agent = configured_agent(user=data_fixture.create_user())
    data_fixture.create_template(workspace=agent.workspace)
    return agent


def get(api_client, token, url):
    return api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")


@pytest.mark.django_db
def test_non_member_reads_the_configuration_of_a_template_agent(
    data_fixture, api_client, template_agent
):
    _, token = data_fixture.create_user_and_token()

    configuration = get(api_client, token, agent_url(template_agent, "configuration"))
    triggers = get(
        api_client,
        token,
        reverse("api:agent:triggers:list", kwargs={"agent_id": template_agent.id}),
    )
    actions = get(
        api_client,
        token,
        reverse("api:agent:actions:list", kwargs={"agent_id": template_agent.id}),
    )

    assert configuration.status_code == 200
    assert configuration.json()["instructions"] == template_agent.instructions
    assert triggers.status_code == 200
    assert actions.status_code == 200


@pytest.fixture
def example_conversations(data_fixture, template_agent):
    """A shared example and a member's private conversation, with a message each."""

    shared = data_fixture.create_agent_conversation(
        agent=template_agent,
        owner_user=None,
        title="Example",
        pinned=True,
        started_by_trigger=False,
        is_example=True,
    )
    data_fixture.create_agent_message(conversation=shared, content="An example")
    private = data_fixture.create_agent_conversation(agent=template_agent)
    data_fixture.create_agent_message(conversation=private, content="PRIVATE")
    return shared, private


def messages_url(agent, conversation):
    return agent_url(agent, "messages", conversation_uuid=conversation.uuid)


@pytest.mark.django_db
def test_non_member_reads_the_example_conversations_of_a_template_agent(
    data_fixture, api_client, template_agent, example_conversations
):
    shared, private = example_conversations
    _, token = data_fixture.create_user_and_token()

    listed = get(api_client, token, agent_url(template_agent, "conversations"))
    messages = get(api_client, token, messages_url(template_agent, shared))
    hidden = get(api_client, token, messages_url(template_agent, private))
    run_as = get(api_client, token, agent_url(template_agent, "run_as_identities"))

    assert listed.status_code == 200
    # Never the private conversation of a member of the template's workspace.
    assert [item["uuid"] for item in listed.json()["results"]] == [str(shared.uuid)]
    assert [item["content"] for item in messages.json()["results"]] == ["An example"]
    assert hidden.status_code == 404
    assert run_as.status_code == 401


@pytest.mark.django_db
def test_non_member_cannot_write_to_a_conversation_of_a_template_agent(
    data_fixture, api_client, template_agent, example_conversations
):
    shared, _ = example_conversations
    _, token = data_fixture.create_user_and_token()

    created = api_client.post(
        agent_url(template_agent, "conversations"),
        new_conversation(),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    sent = api_client.post(
        messages_url(template_agent, shared),
        {"uuid": str(uuid4()), "content": "Hello"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert created.status_code == 401
    assert sent.status_code == 401
    assert shared.messages.count() == 1


@pytest.mark.django_db
def test_non_member_cannot_read_an_agent_outside_a_template(
    data_fixture, api_client, configured_agent
):
    agent = configured_agent(user=data_fixture.create_user())
    _, token = data_fixture.create_user_and_token()

    response = get(api_client, token, agent_url(agent, "configuration"))

    assert response.status_code == 401


@pytest.mark.django_db
def test_allowed_operations_on_templates_include_agent_configuration(data_fixture):
    user = data_fixture.create_user()

    permissions = CoreHandler().get_permissions(user)

    allow_if_template = next(
        manager for manager in permissions if manager["name"] == "allow_if_template"
    )
    assert (
        "agent_application.read_configuration"
        in allow_if_template["permissions"]["allowed_operations_on_templates"]
    )
    assert (
        "agent_application.read_conversations"
        in allow_if_template["permissions"]["allowed_operations_on_templates"]
    )
    assert (
        "agent_application.create_message"
        not in allow_if_template["permissions"]["allowed_operations_on_templates"]
    )


@pytest.mark.django_db
def test_signed_out_visitor_reads_the_setup_of_a_template_agent(
    api_client, template_agent
):
    urls = [
        agent_url(template_agent, "configuration"),
        reverse("api:agent:triggers:list", kwargs={"agent_id": template_agent.id}),
        reverse("api:agent:actions:list", kwargs={"agent_id": template_agent.id}),
    ]

    assert [api_client.get(url).status_code for url in urls] == [200, 200, 200]
    assert api_client.get(
        agent_url(template_agent, "run_as_identities")
    ).status_code in (401, 403)


@pytest.mark.django_db
def test_signed_out_visitor_reads_the_example_conversations_of_a_template_agent(
    api_client, template_agent, example_conversations
):
    shared, private = example_conversations
    # Nobody owns it, like the signed out visitor has no id, but it isn't shared.
    ownerless = shared.__class__.objects.create(
        agent=template_agent, uuid=uuid4(), title="Ownerless", shared=False
    )

    listed = api_client.get(agent_url(template_agent, "conversations"))
    messages = api_client.get(messages_url(template_agent, shared))

    assert listed.status_code == 200
    assert (
        api_client.head(agent_url(template_agent, "conversations")).status_code == 200
    )
    assert [item["uuid"] for item in listed.json()["results"]] == [str(shared.uuid)]
    assert [item["content"] for item in messages.json()["results"]] == ["An example"]
    for hidden in (private, ownerless):
        assert api_client.get(messages_url(template_agent, hidden)).status_code == 404
    assert api_client.post(
        agent_url(template_agent, "conversations"), new_conversation(), format="json"
    ).status_code in (401, 403)


@pytest.mark.django_db
def test_signed_out_visitor_cannot_read_an_agent_outside_a_template(
    data_fixture, api_client, configured_agent
):
    agent = configured_agent(user=data_fixture.create_user())

    response = api_client.get(agent_url(agent, "configuration"))

    assert response.status_code in (401, 403)
    assert "instructions" not in response.json()


@pytest.mark.django_db
def test_signed_out_visitor_cannot_read_conversations_outside_a_template(
    data_fixture, api_client, configured_agent
):
    agent = configured_agent(user=data_fixture.create_user())
    shared = data_fixture.create_agent_conversation(agent=agent, owner_user=None)

    assert api_client.get(agent_url(agent, "conversations")).status_code in (401, 403)
    assert api_client.get(messages_url(agent, shared)).status_code in (401, 403)


@pytest.mark.django_db
def test_signed_out_visitor_reads_the_examples_of_a_user_template(
    data_fixture, api_client, configured_agent
):
    owner = data_fixture.create_user()
    agent = configured_agent(user=owner)
    template = data_fixture.create_user_template(user=owner, workspace=agent.workspace)
    data_fixture.set_user_template_state(template, "public")
    # A user template only gets conversations as the examples of its content.
    example = data_fixture.create_agent_conversation(
        agent=agent,
        owner_user=None,
        shared=True,
        pinned=True,
        started_by_trigger=False,
        is_example=True,
    )
    data_fixture.create_agent_message(conversation=example, content="An example")

    listed = api_client.get(agent_url(agent, "conversations"))
    messages = api_client.get(messages_url(agent, example))

    assert [item["uuid"] for item in listed.json()["results"]] == [str(example.uuid)]
    assert listed.json()["results"][0]["is_example"] is True
    assert [item["content"] for item in messages.json()["results"]] == ["An example"]


@pytest.mark.django_db
def test_a_template_shows_only_its_examples(
    data_fixture, api_client, template_agent, example_conversations
):
    shared, _ = example_conversations
    # Shared, but it didn't come with the template's content.
    other = data_fixture.create_agent_conversation(
        agent=template_agent, owner_user=None, shared=True, title="Not an example"
    )
    _, token = data_fixture.create_user_and_token()

    for headers in ({}, {"HTTP_AUTHORIZATION": f"JWT {token}"}):
        listed = api_client.get(agent_url(template_agent, "conversations"), **headers)
        assert [item["uuid"] for item in listed.json()["results"]] == [str(shared.uuid)]
        hidden = api_client.get(messages_url(template_agent, other), **headers)
        assert hidden.status_code == 404


@pytest.mark.django_db
def test_an_unpinned_example_leaves_the_template_preview(
    api_client, template_agent, example_conversations
):
    shared, _ = example_conversations
    shared.pinned = False
    shared.save()

    listed = api_client.get(agent_url(template_agent, "conversations"))

    assert listed.json()["results"] == []
    assert api_client.get(messages_url(template_agent, shared)).status_code == 404
