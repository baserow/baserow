from django.contrib.auth import get_user_model
from django.db import transaction

from faker import Faker

from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.domains.models import CustomDomain
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import CollectionField
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.models import GridView
from baserow.core.handler import CoreHandler
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.services.registries import service_type_registry

User = get_user_model()


@transaction.atomic
def load_test_data():
    fake = Faker()
    print("Add builder basic data...")

    user = User.objects.get(email="admin@baserow.io")
    workspace = user.workspaceuser_set.get(workspace__name="Acme Corp").workspace

    try:
        builder = Builder.objects.get(
            name="Back to local website", workspace__isnull=False, trashed=False
        )
    except Builder.DoesNotExist:
        builder = CoreHandler().create_application(
            user, workspace, "builder", name="Back to local website"
        )

    CustomDomain.objects.filter(domain_name="test1.getbaserow.io").delete()
    CustomDomain.objects.filter(domain_name="test2.getbaserow.io").delete()
    CustomDomain.objects.filter(domain_name="test3.getbaserow.io").delete()
    CustomDomain.objects.create(
        builder=builder, domain_name="test1.getbaserow.io", order=1
    )
    CustomDomain.objects.create(
        builder=builder, domain_name="test2.getbaserow.io", order=2
    )
    CustomDomain.objects.create(
        builder=builder, domain_name="test3.getbaserow.io", order=3
    )

    integration_type = integration_type_registry.get("local_baserow")

    try:
        integration = Integration.objects.get(
            name="Local baserow", application__trashed=False, application_id=builder.id
        )
    except Integration.DoesNotExist:
        integration = IntegrationHandler().create_integration(
            integration_type, builder, name="Local baserow", authorized_user=user
        )

    heading_element_type = element_type_registry.get("heading")
    text_element_type = element_type_registry.get("text")
    table_element_type = element_type_registry.get("table")
    link_element_type = element_type_registry.get("link")
    header_element = element_type_registry.get("header")
    column_element = element_type_registry.get("column")

    try:
        homepage = Page.objects.get(name="Homepage", builder=builder)
    except Page.DoesNotExist:
        homepage = PageHandler().create_page(builder, "Homepage", "/")

        ElementHandler().create_element(
            heading_element_type, homepage, value='"Back to local"', level=1
        )
        ElementHandler().create_element(
            heading_element_type, homepage, value='"Buy closer, Buy better"', level=2
        )
        content = "\n".join(fake.paragraphs(nb=2))
        ElementHandler().create_element(
            text_element_type,
            homepage,
            value=f'"{content}"',
        )
        ElementHandler().create_element(
            heading_element_type,
            homepage,
            value='"Give more sense to what you eat"',
            level=2,
        )
        content = "\n".join(fake.paragraphs(nb=2))
        ElementHandler().create_element(
            text_element_type,
            homepage,
            value=f'"{content}"',
        )

    try:
        terms = Page.objects.get(name="Terms", builder=builder)
    except Page.DoesNotExist:
        terms = PageHandler().create_page(builder, "Terms", "/terms")

        ElementHandler().create_element(
            heading_element_type, terms, value='"Terms"', level=1
        )
        ElementHandler().create_element(
            heading_element_type, terms, value='"Article 1. General"', level=2
        )
        content = "\n".join(fake.paragraphs(nb=3))
        ElementHandler().create_element(
            text_element_type,
            terms,
            value=f'"{content}"',
        )
        ElementHandler().create_element(
            heading_element_type,
            terms,
            value='"Article 2. Services"',
            level=2,
        )
        content = "\n".join(fake.paragraphs(nb=3))
        ElementHandler().create_element(
            text_element_type,
            terms,
            value=(f'"{content}"'),
        )
        ElementHandler().create_element(
            heading_element_type,
            terms,
            value='"Article 3. Data"',
            level=2,
        )
        content = "\n".join(fake.paragraphs(nb=3))
        ElementHandler().create_element(
            text_element_type,
            terms,
            value=(f'"{content}"'),
        )

        ElementHandler().create_element(
            link_element_type,
            terms,
            value='"Home"',
            variant="button",
            navigation_type="page",
            navigate_to_page_id=homepage.id,
            styles={"button": {"button_alignment": "right"}},
        )

        # Button for homepage
        ElementHandler().create_element(
            link_element_type,
            homepage,
            value='"See terms"',
            variant="button",
            styles={"button": {"button_alignment": "right"}},
            navigation_type="page",
            navigate_to_page_id=terms.id,
        )

        ElementHandler().create_element(
            link_element_type,
            homepage,
            value='"Visit Baserow"',
            variant="link",
            navigation_type="custom",
            target="blank",
            navigate_to_url='"https://baserow.io"',
            styles={"link": {"link_text_alignment": "center"}},
        )

    table = Table.objects.get(
        name="Products",
        database__workspace=workspace,
        database__trashed=False,
    )
    field_name = Field.objects.get(table=table, name="Name")
    field_notes = Field.objects.get(table=table, name="Notes")
    field_category = Field.objects.get(table=table, name="Category")

    try:
        product_detail = Page.objects.get(name="Product detail", builder=builder)
    except Page.DoesNotExist:
        product_detail = PageHandler().create_page(
            builder,
            "Product detail",
            "/product/:id/:name",
            path_params=[
                {"name": "id", "type": "numeric"},
                {"name": "name", "type": "text"},
            ],
        )

        # Data source creation
        service_type = service_type_registry.get("local_baserow_get_row")
        table = Table.objects.get(
            name="Products",
            database__workspace=workspace,
            database__trashed=False,
        )
        view = GridView.objects.create(table=table, order=0, name="Products Grid")

        product_detail_data_source = DataSourceHandler().create_data_source(
            product_detail,
            "Product",
            service_type=service_type,
            view=view,
            table=table,
            integration=integration,
            row_id='get("page_parameter.id")',
        )

        ElementHandler().create_element(
            heading_element_type,
            product_detail,
            value=f'get("data_source.{product_detail_data_source.id}.{field_name.db_column}")',
            level=1,
        )

        ElementHandler().create_element(
            text_element_type,
            product_detail,
            value=(
                f'get("data_source.{product_detail_data_source.id}.{field_notes.db_column}")'
            ),
        )

    try:
        products = Page.objects.get(name="Products", builder=builder)
    except Page.DoesNotExist:
        products = PageHandler().create_page(builder, "Products", "/products")

        # Data source creation
        service_type = service_type_registry.get("local_baserow_list_rows")

        view = GridView.objects.create(table=table, order=0, name="Products Grid 2")

        products_data_source = DataSourceHandler().create_data_source(
            products,
            "Products",
            service_type=service_type,
            view=view,
            table=table,
            integration=integration,
        )

        ElementHandler().create_element(
            heading_element_type, products, value='"All products"', level=1
        )

        table_element = ElementHandler().create_element(
            table_element_type,
            products,
            data_source=products_data_source,
            items_per_page=5,
        )

        fields = [
            {
                "name": "Name",
                "type": "text",
                "config": {
                    "value": f"get('current_record.{field_name.db_column}')",
                },
            },
            {
                "name": "Category",
                "type": "text",
                "config": {
                    "value": f"get('current_record.{field_category.db_column}.value')",
                },
            },
            {
                "name": "Notes",
                "type": "text",
                "config": {
                    "value": f"get('current_record.{field_notes.db_column}')",
                },
            },
            {
                "name": "Details",
                "type": "link",
                "config": {
                    "navigation_type": "page",
                    "navigate_to_page_id": product_detail.id,
                    "navigate_to_url": "",
                    "page_parameters": [
                        {"name": "id", "value": "get('current_record.id')"},
                        {
                            "name": "name",
                            "value": f"get('current_record.{field_name.db_column}')",
                        },
                    ],
                    "link_name": f"get('current_record.{field_name.db_column}')",
                    "target": "self",
                },
            },
        ]
        created_fields = CollectionField.objects.bulk_create(
            [
                CollectionField(**field, order=index)
                for index, field in enumerate(fields)
            ]
        )
        table_element.fields.all().delete()
        table_element.fields.add(*created_fields)

        ElementHandler().create_element(
            link_element_type,
            products,
            value='"Home"',
            variant="button",
            navigation_type="page",
            navigate_to_page_id=homepage.id,
            styles={"button": {"button_alignment": "right"}},
        )

        # Button back from detail page
        ElementHandler().create_element(
            link_element_type,
            product_detail,
            value='"Back to list"',
            variant="button",
            navigation_type="page",
            navigate_to_page_id=products.id,
        )

        # Button back from detail page
        ElementHandler().create_element(
            link_element_type,
            homepage,
            value='"See product list"',
            variant="button",
            navigation_type="page",
            navigate_to_page_id=products.id,
        )

    # Add shared elements
    if builder.shared_page.element_set.count() == 0:
        header = ElementHandler().create_element(
            header_element,
            builder.shared_page,
        )
        column = ElementHandler().create_element(
            column_element, builder.shared_page, parent_element_id=header.id
        )
        ElementHandler().create_element(
            link_element_type,
            builder.shared_page,
            parent_element_id=column.id,
            place_in_container="0",
            value='"Home"',
            variant="link",
            navigation_type="page",
            navigate_to_page_id=homepage.id,
        )
