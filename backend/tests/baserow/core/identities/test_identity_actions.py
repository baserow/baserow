import pytest

from baserow.core.action.registries import action_type_registry
from baserow.core.action.signals import action_done
from baserow.core.identities.actions import UpdateIdentityActionType
from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.service import IdentityService


@pytest.mark.django_db
def test_update_identity_action_records_the_values_it_replaced(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = data_fixture.create_identity(workspace=workspace, name="Runner")
    read_before_the_lock = IdentityHandler().get_identity(identity.id)
    IdentityService().update_identity(user, identity, name="Renamed")
    recorded = []

    def record(sender, action_params, **kwargs):
        recorded.append(action_params)

    action_done.connect(record)
    try:
        action_type_registry.get_by_type(UpdateIdentityActionType).do(
            user, read_before_the_lock, name="Writer"
        )
    finally:
        action_done.disconnect(record)

    assert recorded[0]["original_identity_name"] == "Renamed"
    assert recorded[0]["identity_name"] == "Writer"
