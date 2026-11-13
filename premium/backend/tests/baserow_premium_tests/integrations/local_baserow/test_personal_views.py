import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.builder.action_scopes import PageActionScopeType
from baserow.contrib.builder.data_sources.actions import UpdateDataSourceActionType
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import OWNERSHIP_TYPE_COLLABORATIVE
from baserow.contrib.integrations.local_baserow.integration_types import (
    LocalBaserowIntegrationType,
)
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowGetRowUserServiceType,
    LocalBaserowListRowsUserServiceType,
)
from baserow.core.action.handler import ActionHandler
from baserow_premium.views.models import OWNERSHIP_TYPE_PERSONAL


def _create_views(data_fixture, license_service):
    user = data_fixture.create_user(session_id="session-id")
    workspace = data_fixture.create_workspace(user=user)
    license_service.restrict_user_premium_to(user, workspace.id)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    builder = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        authorized_user=user, application=builder
    )
    collaborative_view = ViewHandler().create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Collaborative",
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )
    personal_view = ViewHandler().create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Personal",
        ownership_type=OWNERSHIP_TYPE_PERSONAL,
    )
    return user, integration, collaborative_view, personal_view


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_get_local_baserow_databases_only_lists_views_usable_by_integrations(
    data_fixture, alternative_per_workspace_license_service
):
    user, integration, collaborative_view, personal_view = _create_views(
        data_fixture, alternative_per_workspace_license_service
    )

    # The authorized user can list both views in the database.
    listed = ViewHandler().list_views(
        user, collaborative_view.table, "grid", False, False, False, False, 10
    )
    assert {view.id for view in listed} == {collaborative_view.id, personal_view.id}

    databases = LocalBaserowIntegrationType.get_local_baserow_databases(integration)

    assert len(databases) == 1
    assert [view.id for view in databases[0].views] == [collaborative_view.id]


@pytest.mark.django_db
@pytest.mark.view_ownership
@pytest.mark.parametrize(
    "service_type_class",
    [LocalBaserowListRowsUserServiceType, LocalBaserowGetRowUserServiceType],
)
def test_local_baserow_view_service_prepare_values_with_personal_view(
    data_fixture, alternative_per_workspace_license_service, service_type_class
):
    user, integration, collaborative_view, personal_view = _create_views(
        data_fixture, alternative_per_workspace_license_service
    )
    service_type = service_type_class()

    values = service_type.prepare_values(
        {
            "view_id": collaborative_view.id,
            "table_id": collaborative_view.table_id,
            "integration_id": integration.id,
        },
        user,
    )
    assert values["view"].id == collaborative_view.id

    with pytest.raises(DRFValidationError) as exc:
        service_type.prepare_values(
            {
                "view_id": personal_view.id,
                "table_id": personal_view.table_id,
                "integration_id": integration.id,
            },
            user,
        )

    assert exc.value.detail["error"] == "invalid_view"
    assert exc.value.detail["detail"] == (
        f"The view with ID {personal_view.id} can't be used because of its "
        "ownership type."
    )


@pytest.mark.django_db
@pytest.mark.view_ownership
def test_local_baserow_view_service_prepare_values_keeps_its_personal_view(
    data_fixture, alternative_per_workspace_license_service
):
    user, integration, collaborative_view, personal_view = _create_views(
        data_fixture, alternative_per_workspace_license_service
    )
    service_type = LocalBaserowListRowsUserServiceType()
    service = data_fixture.create_local_baserow_list_rows_service(
        integration=integration, table=personal_view.table, view=personal_view
    )

    values = service_type.prepare_values(
        {"view_id": personal_view.id}, user, instance=service
    )
    assert values["view"].id == personal_view.id

    # Once another view is used, the personal view can't be set again.
    service.view = collaborative_view
    service.save()
    with pytest.raises(DRFValidationError) as exc:
        service_type.prepare_values(
            {"view_id": personal_view.id}, user, instance=service
        )
    assert exc.value.detail["error"] == "invalid_view"


@pytest.mark.django_db
@pytest.mark.view_ownership
@pytest.mark.undo_redo
def test_update_data_source_using_personal_view_can_be_undone_and_redone(
    data_fixture, alternative_per_workspace_license_service
):
    user, integration, collaborative_view, personal_view = _create_views(
        data_fixture, alternative_per_workspace_license_service
    )
    page = data_fixture.create_builder_page(builder=integration.application)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        table=personal_view.table,
        view=personal_view,
        search_query="'before'",
    )
    scope = [PageActionScopeType.value(page.id)]

    UpdateDataSourceActionType.do(
        user,
        data_source,
        service_type=LocalBaserowListRowsUserServiceType(),
        search_query="'after'",
    )

    undone = ActionHandler.undo(user, scope, "session-id")
    assert [action.error for action in undone] == [None]
    service = data_source.service.specific
    service.refresh_from_db()
    assert service.search_query["formula"] == "'before'"
    assert service.view_id == personal_view.id

    redone = ActionHandler.redo(user, scope, "session-id")
    assert [action.error for action in redone] == [None]
    service.refresh_from_db()
    assert service.search_query["formula"] == "'after'"
    assert service.view_id == personal_view.id
