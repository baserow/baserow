from django.contrib.auth.models import AnonymousUser

import pytest

from baserow.contrib.builder.data_sources.operations import (
    DispatchDataSourceOperationType,
    ListDataSourcesPageOperationType,
)
from baserow.contrib.builder.domains.permission_manager import (
    AllowBuilderPreviewPermissionManagerType,
    AllowPublicBuilderManagerType,
)
from baserow.contrib.builder.elements.operations import (
    ListElementsPageOperationType,
    ReadElementOperationType,
)
from baserow.contrib.builder.pages.operations import UpdatePageOperationType
from baserow.contrib.builder.preview import BuilderPreviewActor
from baserow.contrib.builder.workflow_actions.operations import (
    DispatchBuilderWorkflowActionOperationType,
    ListBuilderWorkflowActionsPageOperationType,
)
from baserow.core.exceptions import PermissionDenied
from baserow.core.operations import (
    ReadApplicationOperationType,
    UpdateApplicationOperationType,
)
from baserow.core.types import PermissionCheck
from baserow.core.user_sources.operations import (
    AuthenticateUserSourceOperationType,
    LoginUserSourceOperationType,
)
from baserow.core.user_sources.user_source_user import UserSourceUser


@pytest.mark.django_db
def test_builder_preview_actor_can_only_read_elements_from_its_builder(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    other_builder = data_fixture.create_builder_application(user=user)
    element = data_fixture.create_builder_heading_element(
        page=data_fixture.create_builder_page(builder=builder)
    )
    other_element = data_fixture.create_builder_heading_element(
        page=data_fixture.create_builder_page(builder=other_builder)
    )
    actor = BuilderPreviewActor(
        builder_id=builder.id,
        workspace_id=builder.workspace_id,
        grant_id=1,
        issued_by_user_id=user.id,
    )
    allowed_check = PermissionCheck(actor, ReadElementOperationType.type, element)
    denied_check = PermissionCheck(actor, ReadElementOperationType.type, other_element)

    result = AllowBuilderPreviewPermissionManagerType().check_multiple_permissions(
        [allowed_check, denied_check], builder.workspace
    )

    assert result[allowed_check] is True
    assert isinstance(result[denied_check], PermissionDenied)


@pytest.mark.django_db
def test_allow_public_builder_manager_type(data_fixture):
    user = data_fixture.create_user(username="Auth user")
    builder = data_fixture.create_builder_application(user=user)
    builder_to = data_fixture.create_builder_application(workspace=None)
    builder_to_2 = data_fixture.create_builder_application(workspace=None)
    domain1 = data_fixture.create_builder_custom_domain(
        builder=builder, published_to=builder_to
    )
    domain2 = data_fixture.create_builder_custom_domain(
        builder=builder, published_to=builder_to_2
    )

    public_page = data_fixture.create_builder_page(builder=builder_to)
    non_public_page = data_fixture.create_builder_page(builder=builder)

    public_data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=public_page
    )
    non_public_data_source = (
        data_fixture.create_builder_local_baserow_get_row_data_source(
            page=non_public_page
        )
    )

    public_user_source = data_fixture.create_user_source_with_first_type(
        application=builder_to
    )
    non_public_user_source = data_fixture.create_user_source_with_first_type(
        application=builder
    )
    other_public_user_source = data_fixture.create_user_source_with_first_type(
        application=builder_to_2
    )

    public_workflow_action = data_fixture.create_notification_workflow_action(
        page=public_page
    )
    non_public_workflow_action = data_fixture.create_notification_workflow_action(
        page=non_public_page
    )

    public_user_source_user = UserSourceUser(
        public_user_source, None, 1, "US public", "e@ma.il"
    )
    non_public_user_source_user = UserSourceUser(
        non_public_user_source, None, 2, "US non public", "e@ma.il"
    )
    other_public_user_source_user = UserSourceUser(
        other_public_user_source, None, 3, "US other public", "e@ma.il"
    )

    public = [
        public_page,
        builder_to.application_ptr,
        public_data_source,
        public_workflow_action,
        public_user_source,
    ]

    perm_manager = AllowPublicBuilderManagerType()
    checks = []
    for user in [
        user,
        public_user_source_user,
        non_public_user_source_user,
        other_public_user_source_user,
        AnonymousUser(),
    ]:
        for perm_type, scope in [
            (ListElementsPageOperationType.type, public_page),
            (ListElementsPageOperationType.type, non_public_page),
            (ListDataSourcesPageOperationType.type, public_page),
            (ListDataSourcesPageOperationType.type, non_public_page),
            (ListBuilderWorkflowActionsPageOperationType.type, public_page),
            (ListBuilderWorkflowActionsPageOperationType.type, non_public_page),
            (UpdatePageOperationType.type, public_page),
            (ReadApplicationOperationType.type, builder_to.application_ptr),
            (ReadApplicationOperationType.type, builder.application_ptr),
            (UpdateApplicationOperationType.type, builder_to.application_ptr),
            (DispatchDataSourceOperationType.type, public_data_source),
            (DispatchDataSourceOperationType.type, non_public_data_source),
            (DispatchBuilderWorkflowActionOperationType.type, public_workflow_action),
            (
                DispatchBuilderWorkflowActionOperationType.type,
                non_public_workflow_action,
            ),
            (
                AuthenticateUserSourceOperationType.type,
                public_user_source,
            ),
            (
                AuthenticateUserSourceOperationType.type,
                non_public_user_source,
            ),
            (
                LoginUserSourceOperationType.type,
                public_user_source,
            ),
            (
                LoginUserSourceOperationType.type,
                non_public_user_source,
            ),
        ]:
            checks.append(PermissionCheck(user, perm_type, scope))

    result = perm_manager.check_multiple_permissions(checks, builder.workspace)

    list_result = [
        (
            c.actor.username,
            c.operation_name,
            "public" if c.context in public else "private",
            result.get(c, None),
        )
        for c in checks
    ]

    assert list_result == [
        ("Auth user", "builder.page.list_elements", "public", True),
        ("Auth user", "builder.page.list_elements", "private", None),
        ("Auth user", "builder.page.list_data_sources", "public", True),
        ("Auth user", "builder.page.list_data_sources", "private", None),
        ("Auth user", "builder.page.list_workflow_actions", "public", True),
        ("Auth user", "builder.page.list_workflow_actions", "private", None),
        ("Auth user", "builder.page.update", "public", None),
        ("Auth user", "application.read", "public", True),
        ("Auth user", "application.read", "private", None),
        ("Auth user", "application.update", "public", None),
        ("Auth user", "builder.page.data_source.dispatch", "public", True),
        ("Auth user", "builder.page.data_source.dispatch", "private", None),
        ("Auth user", "builder.page.workflow_action.dispatch", "public", True),
        ("Auth user", "builder.page.workflow_action.dispatch", "private", None),
        ("Auth user", "application.user_source.authenticate", "public", True),
        ("Auth user", "application.user_source.authenticate", "private", None),
        ("Auth user", "application.user_source.login", "public", None),
        ("Auth user", "application.user_source.login", "private", None),
        ("US public", "builder.page.list_elements", "public", True),
        ("US public", "builder.page.list_elements", "private", None),
        ("US public", "builder.page.list_data_sources", "public", True),
        ("US public", "builder.page.list_data_sources", "private", None),
        ("US public", "builder.page.list_workflow_actions", "public", True),
        ("US public", "builder.page.list_workflow_actions", "private", None),
        ("US public", "builder.page.update", "public", None),
        ("US public", "application.read", "public", True),
        ("US public", "application.read", "private", None),
        ("US public", "application.update", "public", None),
        ("US public", "builder.page.data_source.dispatch", "public", True),
        ("US public", "builder.page.data_source.dispatch", "private", None),
        ("US public", "builder.page.workflow_action.dispatch", "public", True),
        ("US public", "builder.page.workflow_action.dispatch", "private", None),
        ("US public", "application.user_source.authenticate", "public", True),
        ("US public", "application.user_source.authenticate", "private", None),
        ("US public", "application.user_source.login", "public", None),
        ("US public", "application.user_source.login", "private", None),
        ("US non public", "builder.page.list_elements", "public", None),
        ("US non public", "builder.page.list_elements", "private", True),
        ("US non public", "builder.page.list_data_sources", "public", None),
        ("US non public", "builder.page.list_data_sources", "private", True),
        ("US non public", "builder.page.list_workflow_actions", "public", None),
        ("US non public", "builder.page.list_workflow_actions", "private", True),
        ("US non public", "builder.page.update", "public", None),
        ("US non public", "application.read", "public", None),
        ("US non public", "application.read", "private", True),
        ("US non public", "application.update", "public", None),
        ("US non public", "builder.page.data_source.dispatch", "public", None),
        ("US non public", "builder.page.data_source.dispatch", "private", True),
        ("US non public", "builder.page.workflow_action.dispatch", "public", None),
        ("US non public", "builder.page.workflow_action.dispatch", "private", True),
        ("US non public", "application.user_source.authenticate", "public", True),
        ("US non public", "application.user_source.authenticate", "private", None),
        ("US non public", "application.user_source.login", "public", None),
        ("US non public", "application.user_source.login", "private", None),
        ("US other public", "builder.page.list_elements", "public", None),
        ("US other public", "builder.page.list_elements", "private", None),
        ("US other public", "builder.page.list_data_sources", "public", None),
        ("US other public", "builder.page.list_data_sources", "private", None),
        ("US other public", "builder.page.list_workflow_actions", "public", None),
        ("US other public", "builder.page.list_workflow_actions", "private", None),
        ("US other public", "builder.page.update", "public", None),
        ("US other public", "application.read", "public", None),
        ("US other public", "application.read", "private", None),
        ("US other public", "application.update", "public", None),
        ("US other public", "builder.page.data_source.dispatch", "public", None),
        ("US other public", "builder.page.data_source.dispatch", "private", None),
        ("US other public", "builder.page.workflow_action.dispatch", "public", None),
        ("US other public", "builder.page.workflow_action.dispatch", "private", None),
        ("US other public", "application.user_source.authenticate", "public", True),
        ("US other public", "application.user_source.authenticate", "private", None),
        ("US other public", "application.user_source.login", "public", None),
        ("US other public", "application.user_source.login", "private", None),
        ("", "builder.page.list_elements", "public", True),
        ("", "builder.page.list_elements", "private", None),
        ("", "builder.page.list_data_sources", "public", True),
        ("", "builder.page.list_data_sources", "private", None),
        ("", "builder.page.list_workflow_actions", "public", True),
        ("", "builder.page.list_workflow_actions", "private", None),
        ("", "builder.page.update", "public", None),
        ("", "application.read", "public", True),
        ("", "application.read", "private", None),
        ("", "application.update", "public", None),
        ("", "builder.page.data_source.dispatch", "public", True),
        ("", "builder.page.data_source.dispatch", "private", None),
        ("", "builder.page.workflow_action.dispatch", "public", True),
        ("", "builder.page.workflow_action.dispatch", "private", None),
        ("", "application.user_source.authenticate", "public", True),
        ("", "application.user_source.authenticate", "private", None),
        ("", "application.user_source.login", "public", True),
        ("", "application.user_source.login", "private", None),
    ]
