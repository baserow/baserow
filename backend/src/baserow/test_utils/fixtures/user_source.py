from typing import List

from django.contrib.contenttypes.models import ContentType

from baserow.core.user_sources.models import UserSource
from baserow.core.user_sources.registries import (
    UserSourceType,
    user_source_type_registry,
)


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

        kwargs["content_type"] = ContentType.objects.get_for_model(model_class)
        user_source = model_class.objects.create(application=application, **kwargs)

        user_source.uid = user_source.get_type().gen_uid(user_source)
        user_source.save()

        return user_source

    def create_user_sources_with_primary_keys(
        self, user_source_type: UserSourceType, primary_keys: List[int], **kwargs
    ) -> List[UserSource]:
        user_sources = []
        for user_source_id in primary_keys:
            user_source = self.create_user_source(
                user_source_type.model_class, id=user_source_id, **kwargs
            )
            user_sources.append(user_source)
        return user_sources

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

    def create_local_baserow_table_user_source(
        self, application=None, integration=None, table=None, user=None, **kwargs
    ):
        if not application:
            if user is None:
                user = self.create_user()
            application_args = kwargs.pop("application_args", {})
            application = self.create_builder_application(user=user, **application_args)

        if not integration:
            integration = self.create_local_baserow_integration(application=application)

        if not table:
            table, fields, rows = self.build_table(
                user=user,
                columns=[
                    ("Email", "text"),
                    ("Name", "text"),
                    ("Role", "text"),
                ],
                rows=[
                    ["bram@baserow.io", "Bram", ""],
                    ["jrmi@baserow.io", "Jérémie", ""],
                    ["peter@baserow.io", "Peter", ""],
                    ["tsering@baserow.io", "Tsering", ""],
                    ["evren@baserow.io", "Evren", ""],
                ],
            )
            email_field, name_field, role_field = fields
        else:
            email_field = table.field_set.get(name="Email")
            name_field = table.field_set.get(name="Name")
            role_field = table.field_set.get(name="Role")

        local_baserow_user_source_type = user_source_type_registry.get("local_baserow")
        return self.create_user_source(
            local_baserow_user_source_type.model_class,
            application=application,
            integration=integration,
            table=table,
            email_field=email_field,
            name_field=name_field,
            role_field=role_field,
        )
