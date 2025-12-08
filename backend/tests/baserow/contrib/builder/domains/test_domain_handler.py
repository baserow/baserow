import pytest

from baserow.contrib.builder.domains.domain_types import CustomDomainType
from baserow.contrib.builder.domains.exceptions import (
    DomainDoesNotExist,
    DomainNameNotUniqueError,
    DomainNotInBuilder,
)
from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.contrib.builder.domains.models import Domain
from baserow.contrib.builder.exceptions import BuilderDoesNotExist
from baserow.contrib.builder.models import Builder
from baserow.core.cache import global_cache
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
