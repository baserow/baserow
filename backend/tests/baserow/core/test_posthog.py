from unittest.mock import MagicMock, patch

from django.test.utils import override_settings

import pytest

from baserow.core.action.registries import ActionType
from baserow.core.action.signals import ActionCommandType
from baserow.core.posthog import (
    capture_event_action_done,
    capture_user_event,
    get_posthog_client,
)


@pytest.fixture(autouse=True)
def reset_posthog_instance():
    from baserow.core import posthog

    posthog._posthog = None
    yield
    posthog._posthog = None


class TestActionType(ActionType):
    type = "test"
    analytics_params = ["must_be_kept"]

    class Params:
        must_be_kept: str
        must_be_removed: str

    def do(cls, *args, **kwargs):
        pass

    def scope(cls, *args, **kwargs):
        pass


@pytest.mark.django_db
@override_settings(POSTHOG_ENABLED=False)
def test_not_capture_event_if_not_enabled(data_fixture):
    posthog = get_posthog_client()

    assert posthog.disabled is True
    posthog.capture = MagicMock()

    user = data_fixture.create_user()
    capture_user_event(user, "test", {})
    posthog.capture.assert_not_called()


@pytest.mark.django_db
@override_settings(POSTHOG_ENABLED=True)
def test_capture_event_if_enabled(data_fixture):
    posthog = get_posthog_client()

    assert posthog.disabled is False
    posthog.capture = MagicMock()

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    capture_user_event(user, "test", {}, session="session", workspace=workspace)
    posthog.capture.assert_called_once_with(
        distinct_id=user.id,
        event="test",
        properties={
            "user_email": user.email,
            "user_session": "session",
            "workspace_id": workspace.id,
        },
    )


@pytest.mark.django_db
@patch("baserow.core.posthog.capture_user_event")
def test_capture_event_action_done(mock_capture_event, data_fixture):
    user = data_fixture.create_user()

    test_action = TestActionType()
    params = {
        "must_be_kept": "yes",
        "must_be_removed": "yes",
    }
    capture_event_action_done(
        sender=None,
        user=user,
        action_type=test_action,
        action_params=params,
        action_timestamp=None,
        action_command_type=ActionCommandType.DO,
        workspace=None,
        session="session",
    )
    mock_capture_event.assert_called_once_with(
        user,
        "test",
        {"must_be_kept": "yes"},
        workspace=None,
        session="session",
    )
