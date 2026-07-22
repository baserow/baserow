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


@pytest.mark.django_db
def test_aggregate_user_source_counts_per_workspace(data_fixture):
    user = data_fixture.create_user()

    def publish(builder):
        data_fixture.create_builder_custom_domain(
            builder=builder,
            published_to=data_fixture.create_builder_application(workspace=None),
        )

    # Workspace1 has two published builder applications, with two user sources,
    # pointing to the same table.
    workspace1 = data_fixture.create_workspace(user=user)
    builder1a = data_fixture.create_builder_application(workspace=workspace1)
    publish(builder1a)
    user_source1a = data_fixture.create_local_baserow_table_user_source(
        application=builder1a
    )
    builder1b = data_fixture.create_builder_application(workspace=workspace1)
    publish(builder1b)
    data_fixture.create_local_baserow_table_user_source(
        application=builder1b, table=user_source1a.table
    )

    # The table contains 5 rows, and is used twice, so the usage for both is 10.
    assert ApplicationUserUsageHandler().aggregate_user_source_counts(workspace1) == 10

    workspace2 = data_fixture.create_workspace(user=user)
    builder2 = data_fixture.create_builder_application(workspace=workspace2)
    publish(builder2)
    data_fixture.create_local_baserow_table_user_source(application=builder2)

    # The table contains 5 rows, and is used once, so the usage is 5.
    assert ApplicationUserUsageHandler().aggregate_user_source_counts(workspace2) == 5

    # Globally, on this instance, we have a usage of 15.
    assert ApplicationUserUsageHandler().aggregate_user_source_counts() == 15

    # An unpublished application in workspace2 doesn't count towards the quota.
    builder3 = data_fixture.create_builder_application(workspace=workspace2)
    data_fixture.create_local_baserow_table_user_source(application=builder3)
    assert ApplicationUserUsageHandler().aggregate_user_source_counts(workspace2) == 5
