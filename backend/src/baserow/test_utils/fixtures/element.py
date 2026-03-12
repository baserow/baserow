import uuid
from copy import deepcopy

from baserow.contrib.builder.elements.element_types import (
    ButtonElementType,
    CheckboxElementType,
    ChoiceElementType,
    ColumnElementType,
    FormContainerElementType,
    HeadingElementType,
    IFrameElementType,
    ImageElementType,
    InputTextElementType,
    LinkElementType,
    MenuElementType,
    RatingElementType,
    RecordSelectorElementType,
    RepeatElementType,
    TableElementType,
    TextElementType,
)
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import (
    CollectionField,
    MenuItemElement,
)
from baserow.core.cache import local_cache


class ElementFixtures:
    def create_builder_heading_element(self, user=None, page=None, **kwargs):
        return self.create_builder_element(HeadingElementType, user, page, **kwargs)

    def create_builder_text_element(self, user=None, page=None, **kwargs):
        return self.create_builder_element(TextElementType, user, page, **kwargs)

    def create_builder_image_element(self, user=None, page=None, **kwargs):
        return self.create_builder_element(ImageElementType, user, page, **kwargs)

    def create_builder_column_element(self, user=None, page=None, **kwargs):
        return self.create_builder_element(ColumnElementType, user, page, **kwargs)

    def create_builder_link_element(self, user=None, page=None, **kwargs):
        return self.create_builder_element(LinkElementType, user, page, **kwargs)

    def create_builder_input_text_element(self, user=None, page=None, **kwargs):
        return self.create_builder_element(InputTextElementType, user, page, **kwargs)

    def create_builder_checkbox_element(self, user=None, page=None, **kwargs):
        return self.create_builder_element(CheckboxElementType, user, page, **kwargs)

    def create_builder_iframe_element(self, user=None, page=None, **kwargs):
        return self.create_builder_element(IFrameElementType, user, page, **kwargs)

    def create_builder_rating_element(self, user=None, page=None, **kwargs):
        return self.create_builder_element(RatingElementType, user, page, **kwargs)

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
            kwargs["data_source"] = (
                self.create_builder_local_baserow_list_rows_data_source(page=page)
            )

        element = self.create_builder_element(TableElementType, user, page, **kwargs)

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
        return self.create_builder_element(ButtonElementType, user, page, **kwargs)

    def create_builder_form_container_element(self, user=None, page=None, **kwargs):
        return self.create_builder_element(
            FormContainerElementType, user, page, **kwargs
        )

    def create_builder_choice_element(self, user=None, page=None, **kwargs):
        return self.create_builder_element(ChoiceElementType, user, page, **kwargs)

    def create_builder_repeat_element(self, user=None, page=None, **kwargs):
        if "data_source" not in kwargs:
            kwargs["data_source"] = (
                self.create_builder_local_baserow_list_rows_data_source(page=page)
            )
        return self.create_builder_element(RepeatElementType, user, page, **kwargs)

    def create_builder_record_selector_element(self, user=None, page=None, **kwargs):
        if "data_source" not in kwargs:
            kwargs["data_source"] = (
                self.create_builder_local_baserow_list_rows_data_source(page=page)
            )
        return self.create_builder_element(
            RecordSelectorElementType, user, page, **kwargs
        )

    def create_builder_menu_element(self, user=None, page=None, **kwargs):
        return self.create_builder_element(MenuElementType, user, page, **kwargs)

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

    def create_builder_element(self, element_type, user=None, page=None, **kwargs):
        if user is None:
            user = self.create_user()

        if not page:
            builder = kwargs.pop("builder", None)
            page_args = kwargs.pop("page_args", {})
            page = self.create_builder_page(user=user, builder=builder, **page_args)

        [
            last_reference_element,
            last_position,
            last_output,
        ] = page.get_graph().get_last_position()

        # The element is placed at the end of the graph if no position is provided
        reference_element = kwargs.pop("reference_element", last_reference_element)
        position = kwargs.pop("position", last_position)
        output = kwargs.pop("place_in_container", last_output)

        with local_cache.context():  # We make sure the cache is empty
            created_element = ElementHandler().create_element(
                element_type(), page=page, **kwargs
            )
            page.get_graph().insert(
                created_element, reference_element, position, output
            )

        return created_element
