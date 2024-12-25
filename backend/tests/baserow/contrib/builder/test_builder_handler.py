from unittest.mock import MagicMock

from django.contrib.auth import get_user_model

import pytest

from baserow.contrib.builder.handler import CACHE_KEY_PREFIX, BuilderHandler
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.user_sources.user_source_user import UserSourceUser
from tests.baserow.contrib.builder.api.user_sources.helpers import (
    create_user_table_and_role,
)

User = get_user_model()


@pytest.mark.django_db
def test_get_builder(data_fixture):
    builder = data_fixture.create_builder_application()
    assert BuilderHandler().get_builder(builder.id).id == builder.id


@pytest.mark.django_db
def test_get_builder_does_not_exist(data_fixture):
    with pytest.raises(ApplicationDoesNotExist):
        BuilderHandler().get_builder(9999)


@pytest.mark.django_db(transaction=True)
def test_get_builder_select_related_theme_config(
    data_fixture, django_assert_num_queries
):
    builder = data_fixture.create_builder_application()
    builder.colorthemeconfigblock
    builder.typographythemeconfigblock
    builder.buttonthemeconfigblock

    builder = BuilderHandler().get_builder(builder.id)

    with django_assert_num_queries(0):
        builder.colorthemeconfigblock.id
        builder.typographythemeconfigblock.id
        builder.buttonthemeconfigblock.id


@pytest.mark.parametrize(
    "is_anonymous,is_editor_user,user_role,expected_cache_key",
    [
        (
            True,
            False,
            "",
            f"{CACHE_KEY_PREFIX}_100",
        ),
        (
            True,
            False,
            "foo_role",
            f"{CACHE_KEY_PREFIX}_100",
        ),
        (
            False,
            False,
            "foo_role",
            f"{CACHE_KEY_PREFIX}_100_foo_role",
        ),
        (
            False,
            False,
            "bar_role",
            f"{CACHE_KEY_PREFIX}_100_bar_role",
        ),
        # Test the "editor" role
        (
            False,
            True,
            "",
            None,
        ),
    ],
)
def test_get_builder_used_properties_cache_key_returned_expected_cache_key(
    is_anonymous, is_editor_user, user_role, expected_cache_key
):
    """
    Test the BuilderHandler::get_builder_used_properties_cache_key() method.

    Ensure the expected cache key is returned.
    """

    mock_request = MagicMock()

    if is_editor_user:
        mock_request.user = MagicMock(spec=User)

    mock_request.user.is_anonymous = is_anonymous
    mock_request.user.role = user_role

    mock_builder = MagicMock()
    mock_builder.id = 100

    handler = BuilderHandler()

    cache_key = handler.get_builder_used_properties_cache_key(
        mock_request.user, mock_builder
    )

    assert cache_key == expected_cache_key


def test_get_builder_used_properties_cache_key_returns_none():
    """
    Test the BuilderHandler::get_builder_used_properties_cache_key() method.

    Ensure that None is returned when request or builder are not available,
    or if the user is a builder user.
    """

    mock_request = MagicMock()
    mock_request.user = MagicMock(spec=User)

    mock_builder = MagicMock()
    mock_builder.id = 100

    handler = BuilderHandler()

    cache_key = handler.get_builder_used_properties_cache_key(
        mock_request.user, mock_builder
    )

    assert cache_key is None


@pytest.mark.django_db
def test_public_allowed_properties_is_cached(data_fixture, django_assert_num_queries):
    """
    Test the BuilderHandler::public_allowed_properties property.

    Ensure that the expensive call to get_formula_field_names() is cached.
    """

    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("Color", "text"),
        ],
        rows=[
            ["Apple", "Red"],
            ["Banana", "Yellow"],
            ["Cherry", "Purple"],
        ],
    )
    builder = data_fixture.create_builder_application(user=user)

    user_source, integration = create_user_table_and_role(
        data_fixture,
        user,
        builder,
        "foo_user_role",
    )
    user_source_user = UserSourceUser(
        user_source, None, 1, "foo_username", "foo@bar.com", role="foo_user_role"
    )

    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        table=table,
    )
    data_fixture.create_builder_heading_element(
        page=page,
        value=f"get('data_source.{data_source.id}.0.field_{fields[0].id}')",
    )

    handler = BuilderHandler()

    expected_results = {
        "all": {data_source.service.id: [f"field_{fields[0].id}"]},
        "external": {data_source.service.id: [f"field_{fields[0].id}"]},
        "internal": {},
    }

    # Initially calling the property should cause a bunch of DB queries.
    with django_assert_num_queries(12):
        result = handler.get_builder_public_properties(user_source_user, builder)
        assert result == expected_results

    # Subsequent calls to the property should *not* cause any DB queries.
    with django_assert_num_queries(0):
        result = handler.get_builder_public_properties(user_source_user, builder)
        assert result == expected_results
