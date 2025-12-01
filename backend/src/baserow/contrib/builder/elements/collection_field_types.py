from typing import Any, Dict, Generator, TypedDict

from django.core.validators import MinValueValidator

from rest_framework import serializers

from baserow.contrib.builder.elements.element_types import NavigationElementManager
from baserow.contrib.builder.elements.models import CollectionField, LinkElement
from baserow.contrib.builder.elements.registries import CollectionFieldType
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.core.constants import RatingStyleChoices
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW, BaserowFormulaObject
from baserow.core.registry import Instance


class BooleanCollectionFieldType(CollectionFieldType):
    type = "boolean"
    allowed_fields = ["value"]
    serializer_field_names = ["value"]
    simple_formula_fields = ["value"]

    class SerializedDict(TypedDict):
        value: BaserowFormulaObject

    @property
    def serializer_field_overrides(self):
        return {
            "value": FormulaSerializerField(
                help_text="The boolean value.",
                required=False,
            ),
        }


class RatingCollectionFieldType(CollectionFieldType):
    type = "rating"
    allowed_fields = ["value", "color", "rating_style", "max_value"]
    serializer_field_names = ["value", "color", "rating_style", "max_value"]
    simple_formula_fields = ["value"]

    class SerializedDict(TypedDict):
        value: BaserowFormulaObject
        color: str
        rating_style: str
        max_value: int

    @property
    def serializer_field_overrides(self):
        return {
            "value": FormulaSerializerField(
                help_text="The rating value.",
                required=False,
            ),
            "color": serializers.CharField(
                help_text="The color of the rating.",
                required=False,
                allow_blank=True,
                default="primary",
            ),
            "rating_style": serializers.ChoiceField(
                choices=RatingStyleChoices.choices,
                help_text="The style of the rating.",
                required=False,
                default=RatingStyleChoices.STAR,
            ),
            "max_value": serializers.IntegerField(
                help_text="The maximum value of the rating.",
                required=False,
                default=5,
                validators=[MinValueValidator(1)],
            ),
        }


class TextCollectionFieldType(CollectionFieldType):
    type = "text"
    allowed_fields = ["value"]
    serializer_field_names = ["value"]
    simple_formula_fields = ["value"]

    class SerializedDict(TypedDict):
        value: BaserowFormulaObject

    @property
    def serializer_field_overrides(self):
        return {
            "value": FormulaSerializerField(
                help_text="The formula for the text.",
                required=False,
            ),
        }


class LinkCollectionFieldType(CollectionFieldType):
    type = "link"
    simple_formula_fields = NavigationElementManager.simple_formula_fields + [
        "link_name"
    ]

    def after_register(self):
        """
        After the `LinkCollectionFieldType` is registered, we connect the
        `page_deleted` signal to the `page_deleted_update_link_collection_fields`
        receiver. This is so that if the `LinkCollectionFieldType` isn't used, we
        don't execute its handler.
        """

        super(LinkCollectionFieldType, self).after_register()
        from baserow.contrib.builder.elements.receivers import (
            connect_link_collection_field_type_to_page_delete_signal,
        )

        connect_link_collection_field_type_to_page_delete_signal()

    def before_unregister(self):
        """
        Before the `LinkCollectionFieldType` is unregistered, we disconnect the
        `page_deleted` signal from the `page_deleted_update_link_collection_fields`
        receiver.
        """

        super(LinkCollectionFieldType, self).before_unregister()
        from baserow.contrib.builder.elements.receivers import (
            disconnect_link_collection_field_type_from_page_delete_signal,
        )

        disconnect_link_collection_field_type_from_page_delete_signal()

    @property
    def serializer_field_names(self):
        return (
            super().serializer_field_names
            + NavigationElementManager.serializer_field_names
            + [
                "link_name",
                "variant",
            ]
        )

    @property
    def allowed_fields(self):
        return (
            super().allowed_fields
            + NavigationElementManager.allowed_fields
            + [
                "link_name",
                "variant",
            ]
        )

    class SerializedDict(NavigationElementManager.SerializedDict):
        link_name: str
        variant: str

    @property
    def serializer_field_overrides(self):
        return (
            super().serializer_field_overrides
            | NavigationElementManager().get_serializer_field_overrides()
            | {
                "link_name": FormulaSerializerField(
                    help_text="The formula for the link name.",
                    required=False,
                ),
                "variant": serializers.ChoiceField(
                    choices=LinkElement.VARIANTS.choices,
                    help_text=LinkElement._meta.get_field("variant").help_text,
                    required=False,
                    default=LinkElement.VARIANTS.LINK,
                ),
            }
        )

    def formula_generator(
        self, collection_field: CollectionField
    ) -> Generator[str | Instance, str, None]:
        """
        Generator that iterates over formula fields for LinkCollectionFieldType.

        Some formula fields are in the config JSON field, e.g. page_parameters.
        """

        yield from super().formula_generator(collection_field)

        for index, page_parameter in enumerate(
            collection_field.config.get("page_parameters") or []
        ):
            new_formula = yield BaserowFormulaObject.to_formula(
                page_parameter.get("value")
            )
            if new_formula is not None:
                collection_field.config["page_parameters"][index]["value"] = new_formula
                yield collection_field

        for index, query_parameter in enumerate(
            collection_field.config.get("query_parameters") or []
        ):
            new_formula = yield BaserowFormulaObject.to_formula(
                query_parameter.get("value")
            )
            if new_formula is not None:
                collection_field.config["query_parameters"][index][
                    "value"
                ] = new_formula
                yield collection_field

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: Dict[str, Any],
        serialized_values: Dict[str, Any],
        **kwargs,
    ) -> Any:
        return super().deserialize_property(
            prop_name,
            NavigationElementManager().deserialize_property(
                prop_name, value, id_mapping, **kwargs
            ),
            id_mapping,
            serialized_values,
            **kwargs,
        )


class TagsCollectionFieldType(CollectionFieldType):
    type = "tags"
    allowed_fields = ["values", "colors", "colors_is_formula"]
    serializer_field_names = ["values", "colors", "colors_is_formula"]
    simple_formula_fields = ["values"]

    class SerializedDict(TypedDict):
        values: BaserowFormulaObject
        colors_is_formula: bool
        colors: BaserowFormulaObject

    @property
    def serializer_field_overrides(self):
        from baserow.contrib.builder.api.elements.serializers import (
            CollectionFieldOptionalFormulaSerializerField,
        )

        return {
            "values": FormulaSerializerField(
                help_text="The formula for the tags values",
                required=False,
            ),
            "colors": CollectionFieldOptionalFormulaSerializerField(
                help_text="The formula or value for the tags colors",
                required=False,
                is_formula_field_name="colors_is_formula",
            ),
            "colors_is_formula": serializers.BooleanField(
                required=False,
                default=False,
                help_text="Indicates whether the colors is a formula or not.",
            ),
        }

    def formula_generator(
        self, collection_field: CollectionField
    ) -> Generator[str | Instance, str, None]:
        """
        Generator that iterates over formula fields for TagsCollectionFieldType.

        Some formula fields are in the config JSON field. Whether the field is
        a formula field or not is controlled by additional keys.
        """

        yield from super().formula_generator(collection_field)

        is_formula = collection_field.config.get("colors_is_formula", False)
        colors = BaserowFormulaObject.to_formula(
            collection_field.config.get("colors", "")
        )

        if not is_formula:
            colors["mode"] = BASEROW_FORMULA_MODE_RAW

        new_formula = yield colors
        if new_formula is not None:
            collection_field.config["colors"] = new_formula
            yield collection_field


class ButtonCollectionFieldType(CollectionFieldType):
    type = "button"
    allowed_fields = ["label"]
    serializer_field_names = ["label"]
    simple_formula_fields = ["label"]

    class SerializedDict(TypedDict):
        label: BaserowFormulaObject

    @property
    def serializer_field_overrides(self):
        return {
            "label": FormulaSerializerField(
                help_text="The string value.",
                required=False,
            ),
        }

    def before_delete(self, instance: CollectionField):
        # We delete the related workflow actions
        BuilderWorkflowAction.objects.filter(event__startswith=instance.uid).delete()


class ImageCollectionFieldType(CollectionFieldType):
    type = "image"
    allowed_fields = ["src", "alt"]
    serializer_field_names = ["src", "alt"]
    simple_formula_fields = ["src", "alt"]

    class SerializedDict(TypedDict):
        src: BaserowFormulaObject
        alt: BaserowFormulaObject

    @property
    def serializer_field_overrides(self):
        return {
            "src": FormulaSerializerField(
                help_text="A link to the image file",
                required=False,
            ),
            "alt": FormulaSerializerField(
                help_text="A brief text description of the image",
                required=False,
            ),
        }
