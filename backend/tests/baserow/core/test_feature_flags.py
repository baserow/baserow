from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser

import pytest

from baserow.core.exceptions import FeatureDisabledException
from baserow.core.feature_flags import feature_flag_is_enabled
from baserow.core.registries import Plugin, plugin_registry

TEST_FLAG = "test_flag"


class GrantAllButPlugin(Plugin):
    type = "test_grant_all_but"

    def __init__(self, denied_user):
        super().__init__()
        self.denied_user = denied_user

    def get_user_feature_flags(self, user):
        return set() if user == self.denied_user else {TEST_FLAG.upper()}


@pytest.mark.django_db
@pytest.mark.parametrize("instance_flags", [[], [TEST_FLAG], ["*"]])
@pytest.mark.parametrize("actor", ["granted", "not_granted", "anonymous", "none"])
@pytest.mark.parametrize("plugin_registered", [True, False])
def test_feature_flag_is_enabled_per_user(
    data_fixture, settings, instance_flags, actor, plugin_registered
):
    granted = data_fixture.create_user()
    not_granted = data_fixture.create_user()
    user = {
        "granted": granted,
        "not_granted": not_granted,
        "anonymous": AnonymousUser(),
        "none": None,
    }[actor]
    settings.FEATURE_FLAGS = instance_flags
    plugins = {"test": GrantAllButPlugin(not_granted)} if plugin_registered else {}
    expected = bool(instance_flags) or (plugin_registered and actor == "granted")

    with patch.dict(plugin_registry.registry, plugins):
        assert feature_flag_is_enabled(TEST_FLAG, user=user) is expected
        if expected:
            feature_flag_is_enabled(TEST_FLAG, user=user, raise_if_disabled=True)
        else:
            with pytest.raises(FeatureDisabledException):
                feature_flag_is_enabled(TEST_FLAG, user=user, raise_if_disabled=True)
