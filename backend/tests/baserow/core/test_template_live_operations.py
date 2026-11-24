from django.contrib.auth.models import AnonymousUser

import pytest

from baserow.contrib.builder.data_sources.operations import (
    DispatchDataSourceOperationType,
)
from baserow.contrib.dashboard.data_sources.operations import (
    DispatchDashboardDataSourceOperationType,
)
from baserow.core.context import private_link_token
from baserow.core.exceptions import PermissionDenied
from baserow.core.handler import CoreHandler
from baserow.core.registries import permission_manager_type_registry
from baserow.core.types import PermissionCheck
from baserow.core.user_sources.operations import LoginUserSourceOperationType

LIVE_OPERATIONS = [
    DispatchDataSourceOperationType.type,
    DispatchDashboardDataSourceOperationType.type,
    LoginUserSourceOperationType.type,
]
ACTORS = ["anonymous", "signed_in", "author", "admin", "link_holder"]


def live_contexts(data_fixture, workspace):
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    return {
        DispatchDataSourceOperationType.type: (
            data_fixture.create_builder_local_baserow_list_rows_data_source(page=page)
        ),
        DispatchDashboardDataSourceOperationType.type: (
            data_fixture.create_dashboard_data_source(dashboard=dashboard)
        ),
        LoginUserSourceOperationType.type: (
            data_fixture.create_user_source_with_first_type(application=builder)
        ),
    }


def make_templates(data_fixture):
    author = data_fixture.create_user()
    official = data_fixture.create_template()

    public_root = data_fixture.create_user_template(user=author)
    public = data_fixture.create_user_template_revision(public_root)
    data_fixture.set_user_template_state(public_root, "public", revision=public)

    shared = data_fixture.set_user_template_state(
        data_fixture.create_user_template(user=author), "shared"
    )

    templates = {
        "official": (official.workspace, None),
        "user_public": (public.workspace, None),
        "user_private_link": (shared.workspace, shared.private_link_token),
    }
    return author, {
        name: (workspace, token, live_contexts(data_fixture, workspace))
        for name, (workspace, token) in templates.items()
    }


def make_actor(data_fixture, name, author):
    return {
        "anonymous": lambda: AnonymousUser(),
        "signed_in": lambda: data_fixture.create_user(),
        "author": lambda: author,
        "admin": lambda: data_fixture.create_user(is_staff=True),
        "link_holder": lambda: AnonymousUser(),
    }[name]()


def outcome(answer):
    return True if answer is True else type(answer).__name__


@pytest.mark.django_db
def test_live_operations_on_templates(data_fixture):
    author, templates = make_templates(data_fixture)
    manager = permission_manager_type_registry.get("allow_if_template")

    table = {}
    for actor_name in ACTORS:
        actor = make_actor(data_fixture, actor_name, author)
        for template_name, (workspace, token, contexts) in templates.items():
            if actor_name == "link_holder" and token is None:
                continue
            checks = [
                PermissionCheck(actor, operation, contexts[operation])
                for operation in LIVE_OPERATIONS
            ]
            with private_link_token(token):
                answers = CoreHandler().check_multiple_permissions(
                    checks, workspace, return_permissions_exceptions=True
                )
                seam = manager.check_multiple_permissions(checks, workspace)
            for check in checks:
                table[(actor_name, template_name, check.operation_name)] = (
                    outcome(answers[check]),
                    outcome(seam.get(check)),
                )

    granted = {
        (actor_name, "official", operation)
        for actor_name in ["signed_in", "author", "admin"]
        for operation in LIVE_OPERATIONS
    }
    refused = (PermissionDenied.__name__, PermissionDenied.__name__)
    assert len(table) == 39
    assert {
        key: answers
        for key, answers in table.items()
        if answers != ((True, True) if key in granted else refused)
    } == {}
