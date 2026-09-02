from django.contrib.auth import get_user_model

import pytest
from rest_framework import serializers

from baserow.core.user.handler import UserHandler
from baserow.core.user.registries import (
    ChoiceUserPreferenceType,
    user_preference_type_registry,
)


@pytest.mark.django_db
def test_get_user_preferences_returns_defaults_for_untouched_keys(data_fixture):
    user = data_fixture.create_user()

    preferences = UserHandler().get_user_preferences(user)

    assert preferences == user_preference_type_registry.get_defaults()
    assert preferences["all_workspaces_sort_by"] == "last_viewed"
    assert preferences["all_workspaces_view_mode"] == "expanded"


@pytest.mark.django_db
def test_update_user_preferences_merges_and_keeps_unknown_stored_keys_hidden(
    data_fixture,
):
    user = data_fixture.create_user()
    user.profile.preferences = {"removed_type": "x"}
    user.profile.save()

    result = UserHandler().update_user_preferences(
        user, {"all_workspaces_view_mode": "compact"}
    )

    assert result["all_workspaces_view_mode"] == "compact"
    assert result["all_workspaces_sort_by"] == "last_viewed"
    assert "removed_type" not in result
    user.profile.refresh_from_db()
    assert user.profile.preferences == {
        "removed_type": "x",
        "all_workspaces_view_mode": "compact",
    }

    result = UserHandler().update_user_preferences(
        user, {"all_workspaces_sort_by": "name_asc"}
    )
    assert result["all_workspaces_view_mode"] == "compact"
    assert result["all_workspaces_sort_by"] == "name_asc"


def test_choice_preference_type_validates_choices():
    class TestPreferenceType(ChoiceUserPreferenceType):
        type = "test"
        choices = ["a", "b"]
        default = "a"

    field = TestPreferenceType().get_serializer_field()
    assert field.run_validation("b") == "b"
    with pytest.raises(serializers.ValidationError):
        field.run_validation("c")


@pytest.mark.django_db
def test_preferences_work_for_users_without_a_profile():
    # `createsuperuser` and similar paths don't create a profile.
    user = get_user_model().objects.create(
        username="no@profile.com", email="no@profile.com"
    )

    assert (
        UserHandler().get_user_preferences(user)
        == user_preference_type_registry.get_defaults()
    )
    result = UserHandler().update_user_preferences(
        user, {"all_workspaces_view_mode": "compact"}
    )
    assert result["all_workspaces_view_mode"] == "compact"
    assert user.profile.preferences == {"all_workspaces_view_mode": "compact"}
