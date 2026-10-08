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


@pytest.mark.django_db
def test_aggregate_user_source_counts_per_workspace_in_bulk(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()

    def publish(builder):
        data_fixture.create_builder_custom_domain(
            builder=builder,
            published_to=data_fixture.create_builder_application(workspace=None),
        )

    # Two published applications with a user source each, pointing to the same
    # table of 5 rows, so the workspace uses 10.
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

    # One published application with a user source, so the workspace uses 5.
    workspace2 = data_fixture.create_workspace(user=user)
    builder2 = data_fixture.create_builder_application(workspace=workspace2)
    publish(builder2)
    data_fixture.create_local_baserow_table_user_source(application=builder2)

    # Only an unpublished application with a user source: nothing counts.
    workspace3 = data_fixture.create_workspace(user=user)
    builder3 = data_fixture.create_builder_application(workspace=workspace3)
    data_fixture.create_local_baserow_table_user_source(application=builder3)

    # No user source at all.
    workspace4 = data_fixture.create_workspace(user=user)

    # A published user source of a workspace that isn't asked for is left out.
    workspace5 = data_fixture.create_workspace(user=user)
    builder5 = data_fixture.create_builder_application(workspace=workspace5)
    publish(builder5)
    data_fixture.create_local_baserow_table_user_source(application=builder5)

    handler = ApplicationUserUsageHandler()
    workspaces = [workspace1, workspace2, workspace3, workspace4]
    expected_usage = {
        workspace1.id: 10,
        workspace2.id: 5,
        workspace3.id: 0,
        workspace4.id: 0,
    }
    assert handler.aggregate_user_source_counts_per_workspace(workspaces) == (
        expected_usage
    )
    assert handler.aggregate_user_source_counts_per_workspace([]) == {}

    # The bulk usage matches the usage resolved per workspace.
    for workspace in workspaces:
        assert (
            handler.aggregate_user_source_counts(workspace)
            == (expected_usage[workspace.id])
        )

    # Now that the user counts are cached, resolving the usage of all workspaces
    # takes one query for their user sources and one for the specific ones, however
    # many workspaces are asked for.
    with django_assert_num_queries(2):
        assert handler.aggregate_user_source_counts_per_workspace(workspaces) == (
            expected_usage
        )
