import pytest

from baserow.contrib.agent.action_tools.service import AgentActionService
from baserow.contrib.agent.triggers.service import AgentTriggerService
from baserow.contrib.builder.data_sources.service import DataSourceService
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.contrib.dashboard.data_sources.service import DashboardDataSourceService
from baserow.core.integrations.service import IntegrationService
from baserow.core.services.registries import service_type_registry
from baserow.core.user_sources.registries import user_source_type_registry
from baserow.core.user_sources.service import UserSourceService


@pytest.mark.django_db
@pytest.mark.parametrize(
    "own_count,shared_count,expected",
    [
        (0, 0, None),
        (1, 0, "own"),
        (0, 1, "shared"),
        (1, 2, "own"),
        (2, 1, None),
        (0, 2, None),
    ],
)
def test_default_integration_requires_an_unambiguous_choice(
    data_fixture, own_count, shared_count, expected
):
    """Other types and workspaces never affect the integration choice."""
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    shared = data_fixture.create_shared_application(workspace=builder.workspace)
    own = [
        data_fixture.create_smtp_integration(application=builder)
        for _ in range(own_count)
    ]
    workspace = [
        data_fixture.create_smtp_integration(application=shared)
        for _ in range(shared_count)
    ]
    data_fixture.create_local_baserow_integration(
        application=builder, authorized_user=user
    )
    data_fixture.create_smtp_integration(
        application=data_fixture.create_shared_application(user=user)
    )

    selected = IntegrationService().get_default_integration(user, builder, "smtp")

    expected_integration = {"own": own, "shared": workspace}.get(expected, [None])[0]
    assert selected == expected_integration


@pytest.mark.django_db
@pytest.mark.parametrize(
    "kind",
    [
        "builder_action",
        "builder_data",
        "agent_action",
        "agent_trigger",
        "dashboard",
        "user_source",
    ],
)
@pytest.mark.parametrize("shared_only", [False, True])
def test_consumers_preselect_through_the_common_rule(data_fixture, kind, shared_only):
    """Exercise real creation paths, with own and workspace candidates together."""
    user = data_fixture.create_user()
    if kind.startswith("agent"):
        application = data_fixture.create_agent_application(user=user)
    elif kind == "dashboard":
        application = data_fixture.create_dashboard_application(user=user)
    else:
        application = data_fixture.create_builder_application(user=user)
    shared = data_fixture.create_shared_application(workspace=application.workspace)
    if kind == "agent_action":
        create_integration = data_fixture.create_smtp_integration
    else:
        create_integration = data_fixture.create_local_baserow_integration
    workspace_integration = create_integration(application=shared, user=user)
    own = (
        None if shared_only else create_integration(application=application, user=user)
    )

    if kind == "builder_action":
        page = data_fixture.create_builder_page(builder=application)
        values = builder_workflow_action_type_registry.get("create_row").prepare_values(
            {"page": page}, user
        )
        service = values["service"]
    elif kind == "builder_data":
        page = data_fixture.create_builder_page(builder=application)
        service = (
            DataSourceService()
            .create_data_source(
                user, page, service_type_registry.get("local_baserow_list_rows")
            )
            .service
        )
    elif kind == "agent_action":
        service = (
            AgentActionService()
            .create_action(
                user,
                application.id,
                "smtp_email",
                service_values={"use_instance_smtp_settings": False},
            )
            .service
        )
    elif kind == "agent_trigger":
        service = (
            AgentTriggerService()
            .create_trigger(user, application.id, "local_baserow_rows_created")
            .service
        )
    elif kind == "dashboard":
        service = (
            DashboardDataSourceService()
            .create_data_source(
                user,
                application.id,
                service_type_registry.get("local_baserow_aggregate_rows"),
            )
            .service
        )
    else:
        source_type = next(iter(user_source_type_registry.get_all()))
        service = UserSourceService().create_user_source(user, source_type, application)

    expected = own or workspace_integration
    if kind == "agent_trigger" or (kind == "dashboard" and shared_only):
        # Agent row triggers use the run identity; dashboards do not expose shared integrations.
        expected = None
    assert service.integration_id == (expected.id if expected else None)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action_type", ["create_row", "smtp_email", "slack_write_message", "ai_agent"]
)
@pytest.mark.parametrize("explicit", [False, True])
def test_builder_actions_select_a_default_but_preserve_a_choice(
    data_fixture, action_type, explicit
):
    """All service forms get the default, without replacing an explicit choice."""
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder)
    action = builder_workflow_action_type_registry.get(action_type)
    service_type = service_type_registry.get(action.service_type)
    model_class = service_type.get_integration_type().model_class
    own = data_fixture.create_integration(model_class, application=builder)
    shared = data_fixture.create_integration(
        model_class,
        application=data_fixture.create_shared_application(workspace=builder.workspace),
    )
    values = action.prepare_values(
        {
            "page": page,
            "service": {
                **({"integration_id": shared.id} if explicit else {}),
                "use_instance_smtp_settings": False,
            },
        },
        user,
    )
    assert values["service"].integration_id == (shared.id if explicit else own.id)


@pytest.mark.django_db
def test_defaults_do_not_grant_access_or_use_trashed_integrations(data_fixture):
    """Only live integrations the editor may use can become a default."""
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    shared = data_fixture.create_shared_application(workspace=builder.workspace)
    data_fixture.create_smtp_integration(application=builder, trashed=True)
    available = data_fixture.create_smtp_integration(application=shared)
    outsider = data_fixture.create_user()
    selector = IntegrationService()

    assert selector.get_default_integration(outsider, builder, "smtp") is None
    assert selector.get_default_integration(user, builder, "smtp") == available
    assert selector.get_default_integration(user, builder, None) is None


@pytest.mark.django_db
def test_an_ordinary_builder_action_edit_keeps_an_empty_choice(data_fixture):
    """Clearing an integration on an existing action must remain possible."""
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder)
    action_type = builder_workflow_action_type_registry.get("create_row")
    element = data_fixture.create_builder_button_element(page=page)
    action = data_fixture.create_workflow_action(
        action_type.model_class,
        page=page,
        element=element,
        event="click",
        service=action_type.prepare_values({"page": page}, user)["service"],
    )
    data_fixture.create_local_baserow_integration(
        application=builder, authorized_user=user
    )

    values = action_type.prepare_values(
        {"service": {"integration_id": None}}, user, instance=action
    )

    assert values["service"].integration_id is None


@pytest.mark.django_db
def test_instance_smtp_mode_is_not_replaced_by_a_default(data_fixture, settings):
    """Service-specific credential modes take priority over a suggested default."""
    settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST = "smtp.example.com"
    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = True
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder)
    data_fixture.create_smtp_integration(application=builder)

    values = builder_workflow_action_type_registry.get("smtp_email").prepare_values(
        {"page": page, "service": {"use_instance_smtp_settings": True}}, user
    )

    assert values["service"].integration_id is None
    assert values["service"].specific.use_instance_smtp_settings is True


@pytest.mark.django_db
def test_data_source_type_changes_keep_a_compatible_selection(data_fixture):
    """A change of service type does not undo an intentional workspace choice."""
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder)
    shared = data_fixture.create_local_baserow_integration(
        application=data_fixture.create_shared_application(workspace=builder.workspace),
        authorized_user=user,
    )
    data_fixture.create_local_baserow_integration(
        application=builder, authorized_user=user
    )
    service = DataSourceService()
    old_type = service_type_registry.get("local_baserow_list_rows")
    source = service.create_data_source(user, page, old_type, integration_id=shared.id)

    service.update_data_source(
        user,
        source,
        old_type,
        new_service_type=service_type_registry.get("local_baserow_get_row"),
    )
    source.refresh_from_db()

    assert source.service.integration_id == shared.id
