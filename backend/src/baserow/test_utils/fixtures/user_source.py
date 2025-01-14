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
