from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.contrib.builder.domains.domain_types import CustomDomainType
from baserow.contrib.builder.domains.exceptions import (
    DomainDoesNotExist,
    DomainNameNotUniqueError,
    DomainNotInBuilder,
)
from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.contrib.builder.domains.models import Domain
from baserow.contrib.builder.elements.permission_manager import (
    ElementVisibilityPermissionManager,
)
from baserow.contrib.builder.exceptions import BuilderDoesNotExist
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.models import (
    BuilderWorkflowAction,
    EventTypes,
)
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowListRows,
    LocalBaserowUpsertRow,
)
from baserow.core.cache import global_cache
from baserow.core.services.models import Service
from baserow.core.trash.handler import TrashHandler
from baserow.core.user_sources.constants import DEFAULT_USER_ROLE_PREFIX
from baserow.core.utils import Progress


@pytest.mark.django_db
def test_get_domain(data_fixture):
    domain = data_fixture.create_builder_custom_domain()
    assert DomainHandler().get_domain(domain.id).id == domain.id


@pytest.mark.django_db
def test_get_domain_domain_does_not_exist(data_fixture):
    with pytest.raises(DomainDoesNotExist):
        DomainHandler().get_domain(9999)


@pytest.mark.django_db
def test_get_domain_base_queryset(data_fixture, django_assert_num_queries):
    domain = data_fixture.create_builder_custom_domain()

    # Without selecting related
    domain = DomainHandler().get_domain(domain.id)
    with django_assert_num_queries(2):
        workspace = domain.builder.workspace

    # With selecting related
    base_queryset = Domain.objects.select_related("builder", "builder__workspace")
    domain = DomainHandler().get_domain(domain.id, base_queryset=base_queryset)
    with django_assert_num_queries(0):
        workspace = domain.builder.workspace


@pytest.mark.django_db
def test_get_domains(data_fixture):
    builder = data_fixture.create_builder_application()
    domain_one = data_fixture.create_builder_custom_domain(builder=builder)
    domain_two = data_fixture.create_builder_custom_domain(builder=builder)

    domains = list(DomainHandler().get_domains(builder))
    domain_ids = [domain.id for domain in domains]

    assert domain_one.id in domain_ids
    assert domain_two.id in domain_ids
    assert len(domains) == 2


@pytest.mark.django_db
def test_create_domain(data_fixture):
    builder = data_fixture.create_builder_application()
    expected_order = Domain.get_last_order(builder)

    domain = DomainHandler().create_domain(
        CustomDomainType(), builder, domain_name="test.com"
    )

    assert domain.order == expected_order
    assert domain.domain_name == "test.com"


@pytest.mark.django_db
def test_create_domain_with_duplicate_name(data_fixture):
    builder = data_fixture.create_builder_application()
    domain_name = "test.com"

    DomainHandler().create_domain(CustomDomainType(), builder, domain_name=domain_name)

    with pytest.raises(DomainNameNotUniqueError) as exc_info:
        DomainHandler().create_domain(
            CustomDomainType(), builder, domain_name=domain_name
        )

    assert exc_info.value.domain_name == domain_name


@pytest.mark.django_db
def test_delete_domain(data_fixture):
    domain = data_fixture.create_builder_custom_domain()

    DomainHandler().delete_domain(domain)

    assert Domain.objects.count() == 0


@pytest.mark.django_db
def test_update_domain(data_fixture):
    domain = data_fixture.create_builder_custom_domain(domain_name="test.com")

    DomainHandler().update_domain(domain, domain_name="new.com")

    domain.refresh_from_db()

    assert domain.domain_name == "new.com"


@pytest.mark.django_db
def test_update_domain_with_duplicate_name(data_fixture):
    builder = data_fixture.create_builder_application()
    domain = data_fixture.create_builder_custom_domain(
        domain_name="test.com", builder=builder
    )

    existing_domain = "other.com"
    DomainHandler().create_domain(
        CustomDomainType(), builder, domain_name=existing_domain
    )

    with pytest.raises(DomainNameNotUniqueError) as exc_info:
        DomainHandler().update_domain(domain, domain_name=existing_domain)

    assert exc_info.value.domain_name == existing_domain


@pytest.mark.django_db
def test_order_domains(data_fixture):
    builder = data_fixture.create_builder_application()
    domain_one = data_fixture.create_builder_custom_domain(builder=builder, order=1)
    domain_two = data_fixture.create_builder_custom_domain(builder=builder, order=2)

    assert DomainHandler().order_domains(builder, [domain_two.id, domain_one.id]) == [
        domain_two.id,
        domain_one.id,
    ]

    domain_one.refresh_from_db()
    domain_two.refresh_from_db()

    assert domain_one.order == 2
    assert domain_two.order == 1


@pytest.mark.django_db
def test_order_domains_domain_not_in_builder(data_fixture):
    builder = data_fixture.create_builder_application()
    domain_one = data_fixture.create_builder_custom_domain(builder=builder, order=1)
    domain_two = data_fixture.create_builder_custom_domain(builder=builder, order=2)

    base_qs = Domain.objects.filter(id=domain_two.id)

    with pytest.raises(DomainNotInBuilder):
        DomainHandler().order_domains(
            builder, [domain_two.id, domain_one.id], base_qs=base_qs
        )


@pytest.mark.django_db
def test_get_public_builder_by_name(data_fixture):
    builder = data_fixture.create_builder_application()
    builder_to = data_fixture.create_builder_application(workspace=None)
    domain1 = data_fixture.create_builder_custom_domain(
        builder=builder, published_to=builder_to
    )

    result = DomainHandler().get_public_builder_by_domain_name(domain1.domain_name)

    assert builder_to == result


@pytest.mark.django_db
def test_get_published_builder_by_missing_domain_name(data_fixture):
    builder = data_fixture.create_builder_application()
    domain1 = data_fixture.create_builder_custom_domain(builder=builder)

    with pytest.raises(BuilderDoesNotExist):
        DomainHandler().get_public_builder_by_domain_name(domain1.domain_name)


@pytest.mark.django_db
def test_get_published_builder_for_trashed_builder(data_fixture):
    builder = data_fixture.create_builder_application(trashed=True)
    builder_to = data_fixture.create_builder_application(workspace=None)
    domain1 = data_fixture.create_builder_custom_domain(
        builder=builder, published_to=builder_to
    )

    with pytest.raises(BuilderDoesNotExist):
        DomainHandler().get_public_builder_by_domain_name(domain1.domain_name)

    builder = data_fixture.create_builder_application()
    builder_to = data_fixture.create_builder_application(workspace=None)
    domain1 = data_fixture.create_builder_custom_domain(
        builder=builder, published_to=builder_to, trashed=True
    )

    with pytest.raises(BuilderDoesNotExist):
        DomainHandler().get_public_builder_by_domain_name(domain1.domain_name)


@pytest.mark.django_db
def test_domain_publishing(data_fixture):
    builder = data_fixture.create_builder_application()

    domain1 = data_fixture.create_builder_custom_domain(builder=builder)

    page1 = data_fixture.create_builder_page(builder=builder)
    page2 = data_fixture.create_builder_page(builder=builder)

    data_fixture.create_builder_heading_element(page=page1, level=2, value="'foo'")
    data_fixture.create_builder_text_element(page=page1)
    data_fixture.create_builder_heading_element(page=page2)

    progress = Progress(100)

    domain1 = DomainHandler().publish(domain1, progress)

    # Pretend that someone visited the public builder-by-domain endpoint.
    builder_by_domain_cache_key = DomainHandler.get_public_builder_by_domain_cache_key(
        domain1.domain_name
    )

    # We populate the builder domain cache
    global_cache.get(builder_by_domain_cache_key, default="before")

    domain1.refresh_from_db()

    assert domain1.published_to is not None
    assert domain1.published_to.workspace is None
    assert domain1.published_to.visible_pages.count() == builder.visible_pages.count()
    assert domain1.published_to.visible_pages.first().element_set.count() == 2

    assert Builder.objects.count() == 2

    assert progress.progress == progress.total

    # Let's publish it a second time.
    DomainHandler().publish(domain1, progress)

    # Following a re-publish, the builder-by-domain cache is invalidated
    assert global_cache.get(builder_by_domain_cache_key, default="after") == "after"

    assert Builder.objects.count() == 2


@pytest.mark.django_db
def test_get_domain_for_builder(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    builder_to = data_fixture.create_builder_application(workspace=None)
    domain1 = data_fixture.create_builder_custom_domain(
        builder=builder, published_to=builder_to, domain_name="mytest.com"
    )
    domain2 = data_fixture.create_builder_custom_domain(
        builder=builder, domain_name="mytest2.com"
    )

    assert (
        DomainHandler().get_domain_for_builder(builder_to).domain_name == "mytest.com"
    )

    assert DomainHandler().get_domain_for_builder(builder) is None


@pytest.mark.django_db
def test_get_domain_public_url(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    builder_to = data_fixture.create_builder_application(workspace=None)
    domain1 = data_fixture.create_builder_custom_domain(
        builder=builder, published_to=builder_to, domain_name="mytest.com"
    )

    assert domain1.get_public_url() == "http://mytest.com:3000"


@pytest.mark.django_db
def test_get_published_domain_applications(data_fixture):
    user = data_fixture.create_user()

    workspace1 = data_fixture.create_workspace(user=user)
    data_fixture.create_builder_application(workspace=workspace1)
    builder1 = data_fixture.create_builder_application(workspace=workspace1)
    published_builder1 = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder1, published_to=published_builder1
    )

    # Get only published domain applications in workspace1
    published_applications = DomainHandler().get_published_domain_applications(
        workspace1
    )
    assert published_applications.count() == 1
    assert published_applications.contains(published_builder1)

    workspace2 = data_fixture.create_workspace(user=user)
    data_fixture.create_builder_application(workspace=workspace2)
    builder2 = data_fixture.create_builder_application(workspace=workspace2)
    published_builder2 = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder2, published_to=published_builder2
    )

    # Get only published domain applications in workspace2
    published_applications = DomainHandler().get_published_domain_applications(
        workspace2
    )
    assert published_applications.count() == 1
    assert published_applications.contains(published_builder2)

    # Get published domain applications across the instance.
    published_applications = DomainHandler().get_published_domain_applications()
    assert published_applications.count() == 2
    assert published_applications.contains(published_builder1)
    assert published_applications.contains(published_builder2)


@pytest.mark.django_db
@pytest.mark.parametrize("event", ["hover", "button_click"])
def test_domain_publishing_with_invalid_workflow_action_event(data_fixture, event):
    """
    A single workflow action with an event which can't be mapped (e.g. created
    through the API with a bogus value) must not block publishing the builder.
    """

    builder = data_fixture.create_builder_application()
    domain = data_fixture.create_builder_custom_domain(builder=builder)
    page = data_fixture.create_builder_page(builder=builder)
    button = data_fixture.create_builder_button_element(page=page)
    data_fixture.create_notification_workflow_action(
        page=page, element=button, event=event
    )

    domain = DomainHandler().publish(domain)

    published_events = BuilderWorkflowAction.objects.filter(
        page__builder=domain.published_to
    ).values_list("event", flat=True)
    assert list(published_events) == [event]


@pytest.mark.django_db
@pytest.mark.parametrize("role_kind", ["default", "explicit", "explicit_default_name"])
@pytest.mark.parametrize(
    "role_type",
    [Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT, Page.ROLE_TYPES.ALLOW_ALL_EXCEPT],
)
def test_publish_page_roles_follow_user_source(data_fixture, role_kind, role_type):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    source, _ = data_fixture.create_user_table_and_role(user, builder, "editor")
    original_role = f"{DEFAULT_USER_ROLE_PREFIX}{source.id}"
    if role_kind == "default":
        source.role_field = None
        source.save()
    elif role_kind == "explicit_default_name":
        # An explicit role can have the same name as a generated default role.
        source.table.get_model().objects.update(
            **{source.role_field.db_column: original_role}
        )
    else:
        original_role = "editor"
    page = data_fixture.create_builder_page(
        builder=builder,
        path="/home",
        visibility=Page.VISIBILITY_TYPES.LOGGED_IN,
        role_type=role_type,
        roles=[original_role],
    )
    domain = data_fixture.create_builder_custom_domain(builder=builder)

    # Both first publication and republication create a new user source ID.
    for _ in range(2):
        DomainHandler().publish(domain)
        domain.refresh_from_db()
        published_source = domain.published_to.user_sources.get().specific
        published_page = domain.published_to.visible_pages.get(path="/home")
        published_user = published_source.get_type().get_user(
            published_source, email="foo@bar.com"
        )

        assert published_source.id != source.id
        assert published_page.visibility == Page.VISIBILITY_TYPES.LOGGED_IN
        assert published_page.role_type == role_type
        assert ElementVisibilityPermissionManager().actor_can_view_page(
            published_user, published_page
        ) == (role_type == Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT)
        assert published_page.roles == [published_user.role]
        page.refresh_from_db()
        assert page.roles == [original_role]


def _create_builder_with_services(data_fixture, sets, builder=None):
    """
    Creates a builder with `sets` data sources and `sets` workflow actions of
    each of three service action types, all on one integration, plus a trashed
    data source and a trashed workflow action. Returns the builder, the ids of
    all of its services and its number of workflow actions.
    """

    if builder is None:
        builder = data_fixture.create_builder_application(workspace=None)
    page = data_fixture.create_builder_page(builder=builder)
    button = data_fixture.create_builder_button_element(page=page)
    integration = data_fixture.create_local_baserow_integration(application=builder)
    services = []
    actions = 0

    def create_data_source():
        data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
            page=page,
            service=data_fixture.create_local_baserow_list_rows_service(
                integration=integration
            ),
        )
        services.append(data_source.service)
        return data_source

    def create_action(create_action, create_service, **kwargs):
        nonlocal actions
        action = create_action(
            page=page,
            element=button,
            event=EventTypes.CLICK,
            service=create_service(integration=integration),
            **kwargs,
        )
        services.append(action.service)
        actions += 1

    for _ in range(sets):
        create_data_source()
        create_action(
            data_fixture.create_local_baserow_create_row_workflow_action,
            data_fixture.create_local_baserow_upsert_row_service,
        )
        create_action(
            data_fixture.create_local_baserow_update_row_workflow_action,
            data_fixture.create_local_baserow_upsert_row_service,
        )
        create_action(
            data_fixture.create_local_baserow_delete_row_workflow_action,
            data_fixture.create_local_baserow_delete_row_service,
        )

    trashed_data_source = create_data_source()
    trashed_data_source.trashed = True
    trashed_data_source.save()
    create_action(
        data_fixture.create_local_baserow_create_row_workflow_action,
        data_fixture.create_local_baserow_upsert_row_service,
        trashed=True,
    )

    return builder, [service.id for service in services], actions


def _assert_services_deleted(service_ids):
    assert not Service.objects_and_trash.filter(id__in=service_ids).exists()
    assert not LocalBaserowListRows.objects_and_trash.filter(
        id__in=service_ids
    ).exists()
    assert not LocalBaserowUpsertRow.objects_and_trash.filter(
        id__in=service_ids
    ).exists()


@pytest.mark.django_db
def test_delete_published_builder_deletes_all_services_in_one_pass(
    data_fixture, django_capture_on_commit_callbacks
):
    def delete_and_count_queries(builder):
        with (
            CaptureQueriesContext(connection) as ctx,
            django_capture_on_commit_callbacks(execute=True),
        ):
            DomainHandler().delete_published_builder(builder)
        return len(ctx.captured_queries)

    small_builder, small_service_ids, small_actions = _create_builder_with_services(
        data_fixture, 1
    )
    large_builder, large_service_ids, large_actions = _create_builder_with_services(
        data_fixture, 5
    )

    small_queries = delete_and_count_queries(small_builder)
    large_queries = delete_and_count_queries(large_builder)

    assert not Builder.objects.filter(
        id__in=[small_builder.id, large_builder.id]
    ).exists()
    _assert_services_deleted(small_service_ids + large_service_ids)
    # The services are deleted in one batched pass. What's left per service is
    # Django's collector loading each service's parent row while it collects the
    # service subclass rows. Per workflow action, the receiver loads the specific
    # action and then runs a single empty query after commit. Deleting the
    # services one by one costs more than 60 queries per service.
    extra_services = len(large_service_ids) - len(small_service_ids)
    extra_actions = large_actions - small_actions
    assert large_queries <= small_queries + extra_services + 2 * extra_actions


@pytest.mark.django_db
def test_delete_published_builder_refuses_a_workspace_builder(data_fixture):
    builder, service_ids, _ = _create_builder_with_services(
        data_fixture, 1, builder=data_fixture.create_builder_application()
    )

    with pytest.raises(ValueError):
        DomainHandler().delete_published_builder(builder)

    assert Builder.objects.filter(id=builder.id).exists()
    assert Service.objects_and_trash.filter(id__in=service_ids).count() == len(
        service_ids
    )


@pytest.mark.django_db
def test_domain_republishing_deletes_previous_services(
    data_fixture, django_capture_on_commit_callbacks
):
    builder, _, _ = _create_builder_with_services(
        data_fixture, 1, builder=data_fixture.create_builder_application()
    )
    domain = data_fixture.create_builder_custom_domain(builder=builder)

    with django_capture_on_commit_callbacks(execute=True):
        DomainHandler().publish(domain)
    domain.refresh_from_db()
    first_published_to = domain.published_to
    first_service_ids = set(Service.objects_and_trash.values_list("id", flat=True))

    with django_capture_on_commit_callbacks(execute=True):
        DomainHandler().publish(domain)
    domain.refresh_from_db()

    assert not Builder.objects.filter(id=first_published_to.id).exists()
    # Only the services of the builder and of the new publication are left, the
    # same number as after the first publication.
    service_ids = set(Service.objects_and_trash.values_list("id", flat=True))
    assert len(service_ids) == len(first_service_ids)


@pytest.mark.django_db
def test_delete_domain_deletes_published_builder_services(
    data_fixture, django_capture_on_commit_callbacks
):
    builder = data_fixture.create_builder_application()
    published_builder, service_ids, _ = _create_builder_with_services(data_fixture, 1)
    domain = data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )

    with django_capture_on_commit_callbacks(execute=True):
        DomainHandler().delete_domain(domain)

    assert not Builder.objects.filter(id=published_builder.id).exists()
    _assert_services_deleted(service_ids)


@pytest.mark.django_db
def test_trashing_builder_keeps_its_services(
    data_fixture, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    builder, service_ids, _ = _create_builder_with_services(
        data_fixture, 1, builder=builder
    )
    published_builder, published_service_ids, _ = _create_builder_with_services(
        data_fixture, 1
    )
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )

    with django_capture_on_commit_callbacks(execute=True):
        TrashHandler.trash(user, builder.workspace, builder, builder)

    assert Service.objects_and_trash.filter(id__in=service_ids).count() == len(
        service_ids
    )
    assert Service.objects_and_trash.filter(
        id__in=published_service_ids
    ).count() == len(published_service_ids)


@pytest.mark.django_db
def test_permanently_deleting_builder_deletes_all_services(
    data_fixture, django_capture_on_commit_callbacks
):
    builder = data_fixture.create_builder_application()
    builder, service_ids, _ = _create_builder_with_services(
        data_fixture, 1, builder=builder
    )
    published_builder, published_service_ids, _ = _create_builder_with_services(
        data_fixture, 1
    )
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )

    with django_capture_on_commit_callbacks(execute=True):
        TrashHandler.permanently_delete(builder)

    assert not Builder.objects.filter(
        id__in=[builder.id, published_builder.id]
    ).exists()
    _assert_services_deleted(service_ids + published_service_ids)
