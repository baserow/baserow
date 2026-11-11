from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.workflow_actions.models import (
    LocalBaserowUpdateRowWorkflowAction,
)
from baserow.core.trash.handler import TrashHandler


def _list_data_sources(api_client, page, token):
    response = api_client.get(
        reverse("api:builder:data_source:list", kwargs={"page_id": page.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    return {data_source["id"]: data_source for data_source in response.json()}


def _create_other_workspace_table(data_fixture):
    other_user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=other_user)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    status = data_fixture.create_single_select_field(table=table, name="Status")
    data_fixture.create_select_option(field=status, value="Secret", color="red")
    return table


@pytest.mark.django_db
def test_data_sources_dont_describe_a_table_of_another_workspace(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    own_database = data_fixture.create_database_application(
        user=user, workspace=builder.workspace
    )
    own_table = data_fixture.create_database_table(user=user, database=own_database)
    data_fixture.create_text_field(table=own_table, name="Name", primary=True)
    other_table = _create_other_workspace_table(data_fixture)

    # The other workspace's own service describes the table, which caches it.
    legit_service = data_fixture.create_local_baserow_list_rows_service(
        table=other_table
    )
    legit_type = legit_service.get_type()
    assert legit_type.generate_schema(legit_service) is not None
    assert legit_type.get_context_data(legit_service)

    # Like a data source imported with the table id of the instance it came from.
    foreign = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=other_table, integration=integration
    )
    own = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=own_table, integration=integration
    )

    data_sources = _list_data_sources(api_client, page, token)

    assert data_sources[foreign.id]["schema"] is None
    assert data_sources[foreign.id]["context_data"] is None
    assert data_sources[foreign.id]["context_data_schema"] is None
    assert data_sources[own.id]["schema"] is not None


@pytest.mark.django_db
def test_data_sources_without_an_integration_dont_describe_their_table(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    other_table = _create_other_workspace_table(data_fixture)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=other_table, integration=integration
    )

    # Removing the integration for good clears it on the service, which keeps its
    # table. Deleting it from the editor trashes it instead, see the test below.
    integration.delete()
    data_source.service.refresh_from_db()
    assert data_source.service.integration_id is None

    data_sources = _list_data_sources(api_client, page, token)

    assert data_sources[data_source.id]["schema"] is None
    assert data_sources[data_source.id]["context_data"] is None
    assert data_sources[data_source.id]["context_data_schema"] is None


@pytest.mark.django_db
def test_a_button_field_action_without_an_integration_describes_its_table(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    button = data_fixture.create_button_field(table=table, name="Button")
    action = data_fixture.create_database_workflow_action(
        LocalBaserowUpdateRowWorkflowAction, field=button
    )
    service = action.service.specific
    service.table = table
    service.save()

    assert service.integration_id is None
    assert service.get_type().generate_schema(service) is not None


@pytest.mark.django_db
def test_data_sources_with_a_trashed_integration_dont_describe_their_table(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    database = data_fixture.create_database_application(
        user=user, workspace=builder.workspace
    )
    table = data_fixture.create_database_table(user=user, database=database)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=table, integration=integration
    )

    # Deleting an integration trashes it, the service keeps its id.
    TrashHandler.trash(user, builder.workspace, builder, integration)

    data_sources = _list_data_sources(api_client, page, token)

    assert data_sources[data_source.id]["schema"] is None
    assert data_sources[data_source.id]["context_data"] is None
    assert data_sources[data_source.id]["context_data_schema"] is None


@pytest.mark.django_db
def test_data_sources_without_an_integration_describe_a_table_of_their_workspace(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    database = data_fixture.create_database_application(
        user=user, workspace=builder.workspace
    )
    table = data_fixture.create_database_table(user=user, database=database)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=table, integration=None
    )
    assert data_source.service.integration_id is None

    data_sources = _list_data_sources(api_client, page, token)

    assert data_sources[data_source.id]["schema"] is not None
