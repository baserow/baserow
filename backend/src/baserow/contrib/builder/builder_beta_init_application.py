from typing import TYPE_CHECKING, Optional

from django.contrib.contenttypes.models import ContentType
from django.utils import translation
from django.utils.translation import gettext as _

from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import LinkElement
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.workflow_actions.handler import (
    BuilderWorkflowActionHandler,
)
from baserow.contrib.builder.workflow_actions.models import EventTypes
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.contrib.database.fields.models import TextField
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import service_type_registry

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow.contrib.builder.models import Builder
    from baserow.contrib.builder.pages.models import Page
    from baserow.core.integrations.models import Integration


class BuilderApplicationTypeInitApplication:
    """
    Responsible for creating demo content in a new builder application.
    """

    def __init__(self, user: "AbstractUser", application: "Builder"):
        self.user = user
        self.application = application

        with translation.override(user.profile.language):
            self.homepage_name = _("Homepage")
            self.examples_name = _("Examples")
            self.customers_table_name = _("Customers")
            self.first_data_source_name = _("List rows")
            self.first_integration_name = _("Local Baserow")
            self.first_name_field_name = _("Name")
            self.last_name_field_name = _("Last name")

    def get_target_table(self) -> Optional["Table"]:
        """
        Responsible for returning our target table, "Customers" under the
        right conditions, as it can't be modified too much.

        1. The table must still exist.
        2. The name must have not been renamed.
        3. The target user must have permissions to fetch the table.
        4. The target fields we want must still exist, and be a TextField.
        """

        # Sanity check the Customers table exists.
        # If there are multiple, we'll use the first one.
        table = (
            TableHandler()
            .list_workspace_tables(self.user, self.application.workspace)
            .filter(name=self.customers_table_name)
            .order_by("created_on")
            .first()
        )
        if table is None:
            return None

        # If we have a table, ensure it has the two fields we care about.
        content_type = ContentType.objects.get_for_model(TextField)
        target_fields = table.field_set.filter(
            name__in=[self.first_name_field_name, self.last_name_field_name],
            content_type=content_type,
        )
        if target_fields.count() != 2:
            table = None

        return table

    def create_page(self, name: str, path: str) -> "Page":
        return PageHandler().create_page(self.application.specific, name, path)

    def create_integration(self) -> "Integration":
        return IntegrationHandler().create_integration(
            integration_type_registry.get("local_baserow"),
            self.application,
            authorized_user=self.user,
            name=self.first_integration_name,
        )

    def create_intro_element(self, page: "Page", link_to_page: "Page") -> None:
        ElementHandler().create_element(
            element_type_registry.get("heading"),
            page=page,
            level=1,
            value="'Welcome to the Application Builder!'",
        )
        ElementHandler().create_element(
            element_type_registry.get("text"),
            page=page,
            value="\"Baserow's application builder allows you to create dynamic and "
            "complex interface applications with no code. Pages can optionally "
            "source data from this Baserow installation's tables, or you can "
            'add data manually from the General tab."',
        )
        ElementHandler().create_element(
            element_type_registry.get("link"),
            page=page,
            variant="button",
            navigate_to_page_id=link_to_page.id,
            value=f"'Navigate to the {link_to_page.name} page'",
            navigation_type=LinkElement.NAVIGATION_TYPES.PAGE,
        )

    def create_table_element(
        self, page: "Page", table: "Table", integration: "Integration"
    ) -> None:
        first_name_field = table.field_set.get(name=self.first_name_field_name)
        last_name_field = table.field_set.get(name=self.last_name_field_name)

        data_source = DataSourceHandler().create_data_source(
            page,
            self.first_data_source_name,
            service_type_registry.get("local_baserow_list_rows"),
            table=table,
            integration=integration,
        )
        ElementHandler().create_element(
            element_type_registry.get("heading"),
            page=page,
            level=2,
            value="'Tables'",
        )
        ElementHandler().create_element(
            element_type_registry.get("text"),
            page=page,
            value="'Here is an example table sourcing data from the "
            f"{table.name} table.'",
        )
        ElementHandler().create_element(
            element_type_registry.get("table"),
            page=page,
            data_source_id=data_source.id,
            fields=[
                {
                    "name": "Name",
                    "type": "text",
                    "config": {
                        "value": f"get('current_record.{first_name_field.db_column}')"
                    },
                },
                {
                    "name": "Last name",
                    "type": "text",
                    "config": {
                        "value": f"get('current_record.{last_name_field.db_column}')"
                    },
                },
                {
                    "name": "Notes",
                    "type": "text",
                    "config": {
                        "value": "'Some notes about this user.'",
                        "format": "plain",
                    },
                },
            ],
        )

    def create_form_element(
        self, page: "Page", integration: "Integration", table: "Table" = None
    ) -> None:
        ElementHandler().create_element(
            element_type_registry.get("heading"),
            page=page,
            level=2,
            value="'Forms'",
        )
        form_container = ElementHandler().create_element(
            element_type_registry.get("form_container"),
            page=page,
            level=2,
            value="'Forms'",
        )
        first_name_input = ElementHandler().create_element(
            element_type_registry.get("input_text"),
            page=page,
            label="'First name'",
            style_padding_left=0,
            style_padding_right=0,
            placeholder="'Enter your first name'",
            parent_element_id=form_container.id,
        )
        last_name_input = ElementHandler().create_element(
            element_type_registry.get("input_text"),
            page=page,
            label="'Last name'",
            style_padding_left=0,
            style_padding_right=0,
            placeholder="'Enter your last name'",
            parent_element_id=form_container.id,
        )

        # If the `Customers` table's schema didn't change, create a new service,
        # workflow action, and connect it to the new form element.
        if table:
            # Pluck out the first name / last name fields.
            first_name_field = table.field_set.get(name=self.first_name_field_name)
            last_name_field = table.field_set.get(name=self.last_name_field_name)

            # Use the first name as form data on the submit button.
            form_container.submit_button_label = (
                f"concat('Add ', get('form_data.{first_name_input.id}'), ' "
                f"to {table.name} table')"
            )
            form_container.save()

            service = ServiceHandler().create_service(
                service_type_registry.get("local_baserow_upsert_row"),
                table=table,
                integration=integration,
            )
            service.field_mappings.create(
                field=first_name_field, value=f"get('form_data.{first_name_input.id}')"
            )
            service.field_mappings.create(
                field=last_name_field, value=f"get('form_data.{last_name_input.id}')"
            )
            service.save()

            BuilderWorkflowActionHandler().create_workflow_action(
                builder_workflow_action_type_registry.get("create_row"),
                page=page,
                service=service,
                element=form_container,
                event=EventTypes.SUBMIT,
            )
            BuilderWorkflowActionHandler().create_workflow_action(
                builder_workflow_action_type_registry.get("notification"),
                page=page,
                title="'Success!'",
                description=f"concat('Appended ', "
                f"get('form_data.{first_name_input.id}'), ' "
                f"to the {table.name} table')",
                element=form_container,
                event=EventTypes.SUBMIT,
            )
        else:
            # Use the first name as form data on the submit button.
            form_container.submit_button_label = (
                f"concat('Save ', get('form_data.{first_name_input.id}'))"
            )
            form_container.save()

    def create_container_element(self, page: "Page"):
        ElementHandler().create_element(
            element_type_registry.get("heading"),
            page=page,
            level=2,
            value="'Containers'",
        )
        column_element = ElementHandler().create_element(
            element_type_registry.get("column"),
            page=page,
            column_amount=3,
            value="'Containers'",
        )
        ElementHandler().create_element(
            element_type_registry.get("text"),
            page=page,
            place_in_container=0,
            style_padding_left=0,
            style_padding_right=0,
            parent_element_id=column_element.id,
            value="'Elements can be placed in containers...'",
        )
        ElementHandler().create_element(
            element_type_registry.get("text"),
            page=page,
            place_in_container=1,
            style_padding_left=0,
            style_padding_right=0,
            parent_element_id=column_element.id,
            value="'which you can configure with more, or fewer columns.'",
        )
        ElementHandler().create_element(
            element_type_registry.get("text"),
            page=page,
            place_in_container=2,
            style_padding_left=0,
            style_padding_right=0,
            parent_element_id=column_element.id,
            value="'The possibilities are endless!'",
        )
