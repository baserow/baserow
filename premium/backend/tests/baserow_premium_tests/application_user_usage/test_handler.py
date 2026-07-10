import pytest

from baserow_premium.application_user_usage.handler import ApplicationUserUsageHandler


@pytest.mark.django_db
def test_aggregate_user_source_counts(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    # A builder with no domains.
    builder_no_domains = data_fixture.create_builder_application(workspace=workspace)
    data_fixture.create_local_baserow_table_user_source(application=builder_no_domains)
    assert ApplicationUserUsageHandler().aggregate_user_source_counts() == 0

    # A builder with a domain, but it hasn't been published to.
    builder_with_unpublished_domains = data_fixture.create_builder_application(
        workspace=workspace
    )
    data_fixture.create_builder_custom_domain(
        builder=builder_with_unpublished_domains, published_to=None
    )
    data_fixture.create_local_baserow_table_user_source(
        application=builder_with_unpublished_domains
    )
    assert ApplicationUserUsageHandler().aggregate_user_source_counts() == 0

    # A builder with a published domain.
    builder_with_published_domains = data_fixture.create_builder_application(
        workspace=workspace
    )
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder_with_published_domains, published_to=published_builder
    )
    data_fixture.create_local_baserow_table_user_source(
        application=builder_with_published_domains
    )
    assert ApplicationUserUsageHandler().aggregate_user_source_counts() == 5
