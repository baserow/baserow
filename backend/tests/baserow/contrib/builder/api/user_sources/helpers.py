from baserow.core.user_sources.registries import user_source_type_registry


def create_user_table_and_role(
    data_fixture, user, builder, user_role, integration=None
):
    """Helper to create a User table with a particular user role."""

    # Create the user table for the user_source
    user_table, user_fields, user_rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Email", "text"),
            ("Name", "text"),
            ("Password", "text"),
            ("Role", "text"),
        ],
        rows=[
            ["foo@bar.com", "Foo User", "secret", user_role],
        ],
    )
    email_field, name_field, password_field, role_field = user_fields

    integration = integration or data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    user_source = data_fixture.create_user_source(
        user_source_type_registry.get("local_baserow").model_class,
        application=builder,
        integration=integration,
        table=user_table,
        email_field=email_field,
        name_field=name_field,
        role_field=role_field,
    )

    return user_source, integration
