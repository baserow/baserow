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


@pytest.mark.django_db
def test_deleting_workflow_deletes_node_services(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    nodes = [data_fixture.create_automation_node(workflow=workflow) for _ in range(2)]
    service_ids = [node.service_id for node in nodes]

    workflow.delete()

    assert not Service.objects.filter(id__in=service_ids).exists()
