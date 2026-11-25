import pytest

from baserow.core.handler import CoreHandler

from ..utils import agent_url


@pytest.mark.django_db
def test_the_list_marks_and_filters_the_conversations_a_channel_started(
    data_fixture, configured_agent, api_client, api_user
):
    agent = configured_agent(user=api_user)
    visitors = data_fixture.create_channel_conversation(
        channel=data_fixture.create_agent_channel(agent=agent)
    )
    own = data_fixture.create_agent_conversation(user=api_user, agent=agent)

    def listed(**params: str) -> list[tuple[str, bool]]:
        response = api_client.get(agent_url(agent, "conversations"), params)
        return [
            (item["uuid"], item["started_by_channel"])
            for item in response.json()["results"]
        ]

    assert listed(started_by_channel="true") == [(str(visitors.uuid), True)]
    assert listed(started_by_channel="false") == [(str(own.uuid), False)]


@pytest.mark.django_db
def test_a_copied_agent_keeps_the_visitor_conversations_without_their_channel(
    data_fixture, configured_agent
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    conversation = data_fixture.create_channel_conversation(
        channel=data_fixture.create_agent_channel(agent=agent)
    )
    data_fixture.create_agent_message(
        conversation=conversation, role="visitor", content="Hi"
    )

    copied = CoreHandler().duplicate_application(user, agent).specific.conversations

    assert [
        (item.started_by_channel, item.channel_id, item.shared, item.owner_user_id)
        for item in copied.all()
    ] == [(True, None, True, None)]
    assert list(copied.get().messages.values_list("role", "sender_id", "content")) == [
        ("visitor", None, "Hi")
    ]
