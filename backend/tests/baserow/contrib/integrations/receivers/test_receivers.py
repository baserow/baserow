from unittest.mock import patch

import pytest

from baserow.core.integrations.receivers import execute_integration_post_import_hooks

MOCK_LOCAL_BASEROW_PATH = "baserow.contrib.integrations.local_baserow.integration_types.LocalBaserowIntegrationType"


@pytest.mark.django_db
def test_execute_integration_post_import_hooks_returns_early(data_fixture):
    """
    Test the execute_integration_post_import_hooks() receiver.
    Ensure that it returns early if the user is None
    """

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    data_fixture.create_local_baserow_integration(application=application)

    with patch(f"{MOCK_LOCAL_BASEROW_PATH}.after_import") as mock_after_import:
        result = execute_integration_post_import_hooks("", application, None)

    assert result is None
    mock_after_import.assert_not_called()


@pytest.mark.django_db
def test_execute_integration_post_import_hooks_calls_after_import(data_fixture):
    """
    Test the execute_integration_post_import_hooks() receiver.
    Ensure that it calls the integration's after_import() hook.
    """

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(application=application)

    with patch(f"{MOCK_LOCAL_BASEROW_PATH}.after_import") as mock_after_import:
        result = execute_integration_post_import_hooks("", application, user)

    assert result is None
    mock_after_import.assert_called_once_with(
        user,
        integration,
    )
