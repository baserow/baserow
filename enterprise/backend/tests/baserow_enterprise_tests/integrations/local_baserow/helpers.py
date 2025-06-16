from django.contrib.auth.hashers import make_password

from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.core.user_sources.registries import user_source_type_registry
from baserow_enterprise.integrations.local_baserow.models import (
    LocalBaserowPasswordAppAuthProvider,
)


def populate_local_baserow_test_data(data_fixture, role_name="", extra_fields=None):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    domain = data_fixture.create_builder_custom_domain(
        builder=builder,
    )
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    data_fixture.create_database_table(database=database)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )

    columns = [
        ("Email", "text"),
        ("Name", "text"),
        ("Password", "text"),
        ("Role", "text"),
    ]
    extra_args = []
    if extra_fields is not None:
        for item in extra_fields:
            columns.append((item["name"], item["field_type"]))
        extra_args = [i["value"] for i in extra_fields]

    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=columns,
        rows=[
            [
                "test@baserow.io",
                "Test",
                make_password("super not secret"),
                role_name,
                *extra_args,
            ],
            [
                "test2@baserow.io",
                "Test2",
                make_password("super not secret"),
                role_name,
                *extra_args,
            ],
            [
                "test3@baserow.io",
                "Test3",
                make_password("super not secret"),
                role_name,
                *extra_args,
            ],
            ["test4@baserow.io", "Test4", None, role_name, *extra_args],
        ],
    )

    email_field, name_field, password_field, role_field, *other_fields = fields

    local_baserow_user_source_type = user_source_type_registry.get("local_baserow")

    user_source = data_fixture.create_user_source(
        local_baserow_user_source_type.model_class,
        application=builder,
        integration=integration,
        table=table,
        email_field=email_field,
        name_field=name_field,
        role_field=role_field,
    )

    app_auth_provider = data_fixture.create_app_auth_provider(
        LocalBaserowPasswordAppAuthProvider,
        user_source=user_source,
        password_field=password_field,
    )

    domain = DomainHandler().publish(domain)

    published_builder = domain.published_to

    published_user_source = local_baserow_user_source_type.model_class.objects.get(
        application=published_builder
    )
    published_app_auth_provider = LocalBaserowPasswordAppAuthProvider.objects.get(
        user_source=published_user_source
    )

    return {
        "unpublished_user_source": user_source,
        "unpublished_auth_provider": app_auth_provider,
        "user_source": published_user_source,
        "auth_provider": published_app_auth_provider,
        "domain": domain,
        "user_table": table,
        "user": user,
        "rows": rows,
        "fields": fields,
    }
