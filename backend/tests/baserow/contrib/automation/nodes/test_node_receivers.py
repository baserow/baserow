import pytest

from baserow.core.services.models import Service


@pytest.mark.django_db
def test_delete_node_delete_service(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user)

    service = node.service

    node.delete()

    with pytest.raises(Service.DoesNotExist):
        Service.objects.get(id=service.id)
