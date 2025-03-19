import uuid
from copy import deepcopy

from baserow.contrib.builder.elements.models import (
    ButtonElement,
    ChoiceElement,
    CollectionField,
    ColumnElement,
    FormContainerElement,
    HeadingElement,
    ImageElement,
    InputTextElement,
    LinkElement,
    MenuElement,
    MenuItemElement,
    RecordSelectorElement,
    RepeatElement,
    TableElement,
    TextElement,
)


class ElementFixtures:
    def create_builder_heading_element(self, user=None, page=None, **kwargs):
        element = self.create_builder_element(HeadingElement, user, page, **kwargs)
        return element

    def create_builder_text_element(self, user=None, page=None, **kwargs):
        element = self.create_builder_element(TextElement, user, page, **kwargs)
        return element

    def create_builder_image_element(self, user=None, page=None, **kwargs):
        element = self.create_builder_element(ImageElement, user, page, **kwargs)
        return element

    def create_builder_column_element(self, user=None, page=None, **kwargs):
        element = self.create_builder_element(ColumnElement, user, page, **kwargs)
        return element

    def create_builder_link_element(self, user=None, page=None, **kwargs):
        element = self.create_builder_element(LinkElement, user, page, **kwargs)
        return element

    def create_builder_input_text_element(self, user=None, page=None, **kwargs):
        element = self.create_builder_element(InputTextElement, user, page, **kwargs)
        return element

    def create_builder_table_element(self, user=None, page=None, **kwargs):
        fields = kwargs.pop(
            "fields",
            deepcopy(
                [
                    {
                        "name": "Field 1",
                        "type": "text",
                        "config": {"value": "get('test1')"},
                    },
                    {
                        "name": "Field 2",
                        "type": "text",
                        "config": {"value": "get('test2')"},
                    },
                    {
                        "name": "Field 3",
                        "type": "text",
                        "config": {"value": "get('test3')"},
                    },
                ]
            ),
        )

        if "data_source" not in kwargs:
            kwargs[
                "data_source"
            ] = self.create_builder_local_baserow_list_rows_data_source(page=page)

        element = self.create_builder_element(TableElement, user, page, **kwargs)

        if fields:
            created_fields = CollectionField.objects.bulk_create(
                [
                    CollectionField(**field, order=index)
                    for index, field in enumerate(fields)
                ]
            )
            element.fields.add(*created_fields)

        return element

    def create_builder_button_element(self, user=None, page=None, **kwargs):
        element = self.create_builder_element(ButtonElement, user, page, **kwargs)
        return element

    def create_builder_form_container_element(self, user=None, page=None, **kwargs):
        element = self.create_builder_element(
            FormContainerElement, user, page, **kwargs
        )
        return element

    def create_builder_choice_element(self, user=None, page=None, **kwargs):
        element = self.create_builder_element(ChoiceElement, user, page, **kwargs)
        return element

    def create_builder_repeat_element(self, user=None, page=None, **kwargs):
        if "data_source" not in kwargs:
            kwargs[
                "data_source"
            ] = self.create_builder_local_baserow_list_rows_data_source(page=page)
        element = self.create_builder_element(RepeatElement, user, page, **kwargs)
        return element

    def create_builder_record_selector_element(self, user=None, page=None, **kwargs):
        if "data_source" not in kwargs:
            kwargs[
                "data_source"
            ] = self.create_builder_local_baserow_list_rows_data_source(page=page)
        element = self.create_builder_element(
            RecordSelectorElement, user, page, **kwargs
        )
        return element

    def create_builder_menu_element(self, user=None, page=None, **kwargs):
        return self.create_builder_element(MenuElement, user, page, **kwargs)

    def create_builder_menu_element_items(
        self, user=None, page=None, menu_element=None, menu_items=None, **kwargs
    ):
        if not menu_element:
            menu_element = self.create_builder_menu_element(
                user=user, page=page, **kwargs
            )

        if not menu_items:
            menu_items = [
                {
                    "variant": "link",
                    "type": "link",
                    "uid": uuid.uuid4(),
                    "name": "Test Link",
                }
            ]

        created_items = MenuItemElement.objects.bulk_create(
            [
                MenuItemElement(**item, menu_item_order=index)
                for index, item in enumerate(menu_items)
            ]
        )
        menu_element.menu_items.add(*created_items)

        return menu_element

    def create_builder_element(self, model_class, user=None, page=None, **kwargs):
        if user is None:
            user = self.create_user()

        if not page:
            builder = kwargs.pop("builder", None)
            page_args = kwargs.pop("page_args", {})
            page = self.create_builder_page(user=user, builder=builder, **page_args)

        if "order" not in kwargs:
            kwargs["order"] = model_class.get_last_order(page)

        element = model_class.objects.create(page=page, **kwargs)

        return element
