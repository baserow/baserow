from baserow.core.user_sources.registries import user_source_type_registry


class UserSourceFixtures:
    def create_user_source_with_first_type(self, **kwargs):
        first_user_source_type = list(user_source_type_registry.get_all())[0]
        return self.create_user_source(first_user_source_type.model_class, **kwargs)

    def create_user_source(self, model_class, user=None, application=None, **kwargs):
        if not application:
            if user is None:
                user = self.create_user()

            application_args = kwargs.pop("application_args", {})
            application = self.create_builder_application(user=user, **application_args)

        if "order" not in kwargs:
            kwargs["order"] = model_class.get_last_order(application)

        user_source = model_class.objects.create(application=application, **kwargs)

        return user_source

    def create_user_table_and_role(self, user, builder, user_role, integration=None):
        """Helper to create a User table with a particular user role."""

        # Create the user table for the user_source
        user_table, user_fields, user_rows = self.build_table(
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

        integration = integration or self.create_local_baserow_integration(
            user=user, application=builder
        )
        user_source = self.create_user_source(
            user_source_type_registry.get("local_baserow").model_class,
            application=builder,
            integration=integration,
            table=user_table,
            email_field=email_field,
            name_field=name_field,
            role_field=role_field,
        )

        return user_source, integration
