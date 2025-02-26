from django.contrib.auth.models import AnonymousUser
from django.test.utils import override_settings

import pytest

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.data_sources.operations import (
    DispatchDataSourceOperationType,
    ListDataSourcesPageOperationType,
)
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.elements.operations import ListElementsPageOperationType
from baserow.contrib.builder.operations import ListPagesBuilderOperationType
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.contrib.builder.workflow_actions.operations import (
    ListBuilderWorkflowActionsPageOperationType,
)
from baserow.core.handler import CoreHandler
from baserow.core.types import PermissionCheck


@pytest.mark.django_db
@pytest.mark.django_db
@override_settings(
    PERMISSION_MANAGERS=[
        "core",
        "setting_operation",
        "staff",
        "allow_if_template",
        "member",
        "token",
        "role",
        "basic",
    ]
)
def test_allow_if_template_permission_manager(data_fixture):
    buser = data_fixture.create_user(username="Auth user")

    workspace_0 = data_fixture.create_workspace(user=buser)

    workspace_1 = data_fixture.create_workspace()
    application_1 = data_fixture.create_builder_application(workspace=workspace_1)
    page_1 = data_fixture.create_builder_page(builder=application_1)
    element_1 = data_fixture.create_builder_text_element(page=page_1)
    workflow_action_1 = data_fixture.create_local_baserow_update_row_workflow_action(
        element=element_1, page=page_1
    )
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        builder=application_1
    )

    workspace_2 = data_fixture.create_workspace()
    data_fixture.create_template(workspace=workspace_2)
    application_2 = data_fixture.create_builder_application(workspace=workspace_2)
    page_2 = data_fixture.create_builder_page(builder=application_2)
    element_2 = data_fixture.create_builder_text_element(page=page_2)
    workflow_action_2 = data_fixture.create_local_baserow_update_row_workflow_action(
        element=element_2, page=page_2
    )
    data_source_2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        builder=application_2
    )

    template = [
        workspace_2,
        application_2,
        page_2,
        element_2,
        workflow_action_2,
        data_source_2,
    ]

    checks = []
    for user in [
        buser,
        AnonymousUser(),
    ]:
        for perm_type, scope in [
            (ListPagesBuilderOperationType.type, application_1),
            (ListElementsPageOperationType.type, page_1),
            (ListBuilderWorkflowActionsPageOperationType.type, page_1),
            (DispatchDataSourceOperationType.type, data_source_1),
            (ListDataSourcesPageOperationType.type, application_1),
        ]:
            checks.append(PermissionCheck(user, perm_type, scope))

    result_1 = CoreHandler().check_multiple_permissions(checks, workspace_1)

    list_result_1 = [
        (
            c.actor.username or "Anonymous",
            c.operation_name,
            "template" if c.context in template else "Not a template",
            result_1.get(c, None),
        )
        for c in checks
    ]

    checks = []
    for user in [
        buser,
        AnonymousUser(),
    ]:
        for perm_type, scope in [
            (ListPagesBuilderOperationType.type, application_2),
            (ListElementsPageOperationType.type, page_2),
            (ListBuilderWorkflowActionsPageOperationType.type, page_2),
            (DispatchDataSourceOperationType.type, data_source_2),
            (ListDataSourcesPageOperationType.type, application_2),
        ]:
            checks.append(PermissionCheck(user, perm_type, scope))

    result_2 = CoreHandler().check_multiple_permissions(checks, workspace_2)

    list_result_2 = [
        (
            c.actor.username or "Anonymous",
            c.operation_name,
            "template" if c.context in template else "Not a template",
            result_2.get(c, None),
        )
        for c in checks
    ]

    list_result = list_result_1 + list_result_2

    assert list_result == [
        ("Auth user", "builder.list_pages", "Not a template", False),
        ("Auth user", "builder.page.list_elements", "Not a template", False),
        ("Auth user", "builder.page.list_workflow_actions", "Not a template", False),
        ("Auth user", "builder.page.data_source.dispatch", "Not a template", False),
        ("Auth user", "builder.page.list_data_sources", "Not a template", False),
        ("Anonymous", "builder.list_pages", "Not a template", False),
        ("Anonymous", "builder.page.list_elements", "Not a template", False),
        ("Anonymous", "builder.page.list_workflow_actions", "Not a template", False),
        ("Anonymous", "builder.page.data_source.dispatch", "Not a template", False),
        ("Anonymous", "builder.page.list_data_sources", "Not a template", False),
        ("Auth user", "builder.list_pages", "template", True),
        ("Auth user", "builder.page.list_elements", "template", True),
        ("Auth user", "builder.page.list_workflow_actions", "template", True),
        ("Auth user", "builder.page.data_source.dispatch", "template", True),
        ("Auth user", "builder.page.list_data_sources", "template", True),
        ("Anonymous", "builder.list_pages", "template", True),
        ("Anonymous", "builder.page.list_elements", "template", True),
        ("Anonymous", "builder.page.list_workflow_actions", "template", True),
        ("Anonymous", "builder.page.data_source.dispatch", "template", True),
        ("Anonymous", "builder.page.list_data_sources", "template", True),
    ]


@pytest.mark.django_db
@pytest.mark.django_db
@override_settings(
    PERMISSION_MANAGERS=[
        "core",
        "setting_operation",
        "staff",
        "allow_if_template",
        "member",
        "token",
        "role",
        "basic",
    ]
)
def test_allow_if_template_permission_manager_filter_queryset(data_fixture):
    user = data_fixture.create_user(username="Auth user")

    workspace_0 = data_fixture.create_workspace(user=user)

    workspace_1 = data_fixture.create_workspace()
    application_1 = data_fixture.create_builder_application(workspace=workspace_1)
    page_1 = data_fixture.create_builder_page(builder=application_1)
    element_1 = data_fixture.create_builder_text_element(page=page_1)
    workflow_action_1 = data_fixture.create_local_baserow_update_row_workflow_action(
        element=element_1, page=page_1
    )
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page_1
    )

    workspace_2 = data_fixture.create_workspace()
    data_fixture.create_template(workspace=workspace_2)
    application_2 = data_fixture.create_builder_application(workspace=workspace_2)
    shared_page_2 = application_2.shared_page
    page_2 = data_fixture.create_builder_page(builder=application_2)
    element_2 = data_fixture.create_builder_text_element(page=page_2)
    workflow_action_2 = data_fixture.create_local_baserow_update_row_workflow_action(
        element=element_2, page=page_2
    )
    data_source_2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page_2
    )

    tests_w1 = [
        (
            ListPagesBuilderOperationType.type,
            Page.objects.filter(builder__workspace=workspace_1),
        ),
        (
            ListElementsPageOperationType.type,
            Element.objects.filter(page__builder__workspace=workspace_1),
        ),
        (
            ListBuilderWorkflowActionsPageOperationType.type,
            BuilderWorkflowAction.objects.filter(page__builder__workspace=workspace_1),
        ),
        (
            ListDataSourcesPageOperationType.type,
            DataSource.objects.filter(page__builder__workspace=workspace_1),
        ),
    ]

    for operation_name, queryset in tests_w1:
        assert (
            sorted(
                [
                    a.id
                    for a in CoreHandler().filter_queryset(
                        user,
                        operation_name,
                        queryset,
                        workspace=workspace_1,
                    )
                ]
            )
            == []
        )

    tests_w1 = [
        (
            ListPagesBuilderOperationType.type,
            Page.objects.filter(builder__workspace=workspace_2),
            [shared_page_2.id, page_2.id],
        ),
        (
            ListElementsPageOperationType.type,
            Element.objects.filter(page__builder__workspace=workspace_2),
            [element_2.id],
        ),
        (
            ListBuilderWorkflowActionsPageOperationType.type,
            BuilderWorkflowAction.objects.filter(page__builder__workspace=workspace_2),
            [workflow_action_2.id],
        ),
        (
            ListDataSourcesPageOperationType.type,
            DataSource.objects.filter(page__builder__workspace=workspace_2),
            [data_source_2.id],
        ),
    ]

    for operation_name, queryset, expected in tests_w1:
        assert (
            sorted(
                [
                    a.id
                    for a in CoreHandler().filter_queryset(
                        user,
                        operation_name,
                        queryset,
                        workspace=workspace_2,
                    )
                ]
            )
            == expected
        ), operation_name
