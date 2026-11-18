from django.urls import reverse

import pytest

from baserow.core.handler import CoreHandler

from .utils import agent_url


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


@pytest.mark.django_db
def test_non_member_cannot_read_conversations_of_a_template_agent(
    data_fixture, api_client, template_agent
):
    _, token = data_fixture.create_user_and_token()

    response = get(api_client, token, agent_url(template_agent, "conversations"))
    run_as = get(api_client, token, agent_url(template_agent, "run_as_identities"))

    assert response.status_code == 401
    assert run_as.status_code == 401


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
    assert api_client.get(agent_url(template_agent, "conversations")).status_code in (
        401,
        403,
    )


@pytest.mark.django_db
def test_signed_out_visitor_cannot_read_an_agent_outside_a_template(
    data_fixture, api_client, configured_agent
):
    agent = configured_agent(user=data_fixture.create_user())

    response = api_client.get(agent_url(agent, "configuration"))

    assert response.status_code in (401, 403)
    assert "instructions" not in response.json()
