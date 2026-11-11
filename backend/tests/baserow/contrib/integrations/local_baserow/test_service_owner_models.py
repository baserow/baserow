from django.apps import apps

import pytest

from baserow.contrib.database.workflow_actions.models import (
    LocalBaserowUpdateRowWorkflowAction,
)
from baserow.contrib.integrations.local_baserow.service_types import (
    get_service_owner_models,
)
from baserow.core.services.models import (
    Service,
    ServiceFilter,
    ServiceFilterGroup,
    ServiceSort,
)

# Models that hold a service as a part of it, rather than the service being part of
# them.
SERVICE_PART_MODELS = {
    "integrations.LocalBaserowTableServiceFieldMapping",
    "baserow_premium.LocalBaserowTableServiceAggregationSeries",
    "baserow_premium.LocalBaserowTableServiceAggregationGroupBy",
    "baserow_premium.LocalBaserowTableServiceAggregationSortBy",
}


def test_every_service_owner_is_known():
    """
    A service without an integration is only described when the application it's
    part of is found, see `LocalBaserowTableServiceType.can_describe_table`. A new
    model holding a service must be added to `get_service_owner_models`, or to the
    parts above, otherwise its services silently lose their schema.
    """

    owner_models = get_service_owner_models()
    known_owners = (
        owner_models.single + owner_models.button_actions + owner_models.builder_actions
    )

    unknown = []
    for model in apps.get_models():
        if model._meta.abstract or issubclass(model, Service):
            continue
        for field in model._meta.concrete_fields:
            # A model pointing at a specific service type is a part of it.
            if not field.is_relation or field.related_model is not Service:
                continue
            if (
                issubclass(model, known_owners)
                or issubclass(model, (ServiceFilter, ServiceFilterGroup, ServiceSort))
                or model._meta.label in SERVICE_PART_MODELS
            ):
                continue
            unknown.append(f"{model._meta.label}.{field.name}")

    assert unknown == []


def _create_tables(data_fixture, user, workspace):
    """A table of the workspace, and one of another workspace."""

    database = data_fixture.create_database_application(user=user, workspace=workspace)
    own_table = data_fixture.create_database_table(user=user, database=database)
    data_fixture.create_text_field(table=own_table, name="Name", primary=True)
    other_table = data_fixture.create_database_table(user=data_fixture.create_user())
    data_fixture.create_text_field(table=other_table, name="Name", primary=True)
    return own_table, other_table


def _schema(service):
    return service.get_type().generate_schema(service.specific)


@pytest.mark.django_db
def test_an_automation_node_without_an_integration_describes_its_workspace_table(
    data_fixture,
):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(user, automation=automation)
    own_table, other_table = _create_tables(data_fixture, user, automation.workspace)

    own = data_fixture.create_local_baserow_create_row_action_node(
        user=user,
        workflow=workflow,
        service_kwargs={"integration": None, "table": own_table},
    )
    other = data_fixture.create_local_baserow_create_row_action_node(
        user=user,
        workflow=workflow,
        service_kwargs={"integration": None, "table": other_table},
    )

    assert _schema(own.service) is not None
    assert _schema(other.service) is None


@pytest.mark.django_db
def test_a_dashboard_data_source_without_an_integration_describes_its_workspace_table(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    own_table, other_table = _create_tables(data_fixture, user, dashboard.workspace)

    own = data_fixture.create_dashboard_local_baserow_list_rows_data_source(
        dashboard=dashboard, table=own_table, integration=None
    )
    other = data_fixture.create_dashboard_local_baserow_list_rows_data_source(
        dashboard=dashboard, table=other_table, integration=None
    )

    assert _schema(own.service) is not None
    assert _schema(other.service) is None


@pytest.mark.django_db
def test_a_builder_action_without_an_integration_describes_its_workspace_table(
    data_fixture,
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    own_table, other_table = _create_tables(data_fixture, user, builder.workspace)

    own = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page,
        service=data_fixture.create_local_baserow_upsert_row_service(
            integration=None, table=own_table
        ),
    )
    other = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page,
        service=data_fixture.create_local_baserow_upsert_row_service(
            integration=None, table=other_table
        ),
    )

    assert _schema(own.service) is not None
    assert _schema(other.service) is None


@pytest.mark.django_db
def test_finding_the_owner_of_a_button_field_action_takes_few_queries(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button = data_fixture.create_button_field(table=table, name="Button")
    action = data_fixture.create_database_workflow_action(
        LocalBaserowUpdateRowWorkflowAction, field=button
    )
    service = action.service.specific

    # One query per single owner, then one for all the button field actions.
    with django_assert_num_queries(4):
        assert service.get_type()._get_owner_workspace_id(service) == (True, None)
