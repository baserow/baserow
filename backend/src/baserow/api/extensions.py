from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.plumbing import force_instance


class MappingSerializerExtension(OpenApiSerializerExtension):
    """
    This OpenAPI serializer extension makes it possible to easily define a mapping of
    serializers. The anyOf attribute will be used, which will give users the option
    to choose a response type without having a discriminator field. It can be used
    for a response and request.

    Example:
        @auto_schema(
            responses={
                200: MappingSerializer(
                    "Applications",
                    {
                        'car': CarSerializer,
                        'boat': BoatSerializer
                    }
                ),
            }
        )
    """

    target_class = "baserow.api.utils.MappingSerializer"

    def get_name(self):
        return self.target.component_name

    def map_serializer(self, auto_schema, direction):
        return self._map_serializer(auto_schema, direction, self.target.mapping)

    def _map_serializer(self, auto_schema, direction, mapping):
        sub_components = []

        for key, serializer_class in mapping.items():
            sub_serializer = force_instance(serializer_class)
            resolved_sub_serializer = auto_schema.resolve_serializer(
                sub_serializer, direction
            )
            sub_components.append((key, resolved_sub_serializer.ref))

        return {"anyOf": [ref for _, ref in sub_components]}


class CustomFieldRegistryMappingSerializerExtension(MappingSerializerExtension):
    """
    This OpenAPI serializer extension automatically generates a mapping of the
    `CustomFieldsInstanceMixin` in the `CustomFieldsRegistryMixin`. The anyOf attribute
    will be used, which will give users the option to choose a response type without
    having a discriminator field. It can be used for a response and request.

    Example:
        @auto_schema(
            responses={
                200: CustomFieldRegistryMappingSerializer(
                    'ExampleName',
                    field_type_registry,
                    many=True
                ),
            }
        )
    """

    target_class = "baserow.api.utils.CustomFieldRegistryMappingSerializer"

    def get_name(self):
        part_1 = self.target.registry.name.title()
        part_2 = self.target.base_class.__name__
        return f"{part_1}{part_2}"

    def map_serializer(self, auto_schema, direction):
        try:
            base_ref_name = getattr(getattr(self.target.base_class, "Meta"), "ref_name")
        except AttributeError:
            base_ref_name = None

        mapping = {
            types.type: types.get_serializer_class(
                base_class=self.target.base_class,
                meta_ref_name=(
                    f"{types.type}_{base_ref_name}" if base_ref_name else None
                ),
                request_serializer=self.target.request,
            )
            for types in self.target.registry.registry.values()
        }

        return self._map_serializer(auto_schema, direction, mapping)


class DiscriminatorMappingSerializerExtension(OpenApiSerializerExtension):
    """
    This OpenAPI serializer extension makes it possible to easily define polymorphic
    relationships. It can be used for a response and request.

    Example:
        @auto_schema(
            responses={
                200: DiscriminatorMappingSerializer(
                    'ExampleName',
                    {
                        'car': CarSerializer,
                        'boat': BoatSerializer
                    },
                    many=True
                ),
            }
        )
    """

    target_class = "baserow.api.utils.DiscriminatorMappingSerializer"

    def get_name(self):
        return self.target.component_name

    def map_serializer(self, auto_schema, direction):
        return self._map_serializer(auto_schema, direction, self.target.mapping)

    def _map_serializer(self, auto_schema, direction, mapping):
        sub_components = []

        for key, serializer_class in mapping.items():
            sub_serializer = force_instance(serializer_class)
            resolved = auto_schema.resolve_serializer(sub_serializer, direction)
            schema = resolved.ref

            if isinstance(schema, list):
                for item in schema:
                    sub_components.append((key, item))
            else:
                sub_components.append((key, schema))

        return {
            "oneOf": [schema for _, schema in sub_components],
            "discriminator": {
                "propertyName": self.target.type_field_name,
                "mapping": {
                    key: value["$ref"]
                    for key, value in sub_components
                    if isinstance(value, dict) and "$ref" in value
                },
            },
        }


class DiscriminatorCustomFieldsMappingSerializerExtension(
    DiscriminatorMappingSerializerExtension
):
    """
    This OpenAPI serializer extension automatically generates a mapping of the
    `CustomFieldsInstanceMixin` in the `CustomFieldsRegistryMixin`. The type will be
    the key and the serializer will be the value.

    Example:
        @auto_schema(
            responses={
                200: DiscriminatorCustomFieldsMappingSerializer(
                    'ExampleName',
                    field_type_registry,
                    many=True
                ),
            }
        )
    """

    target_class = "baserow.api.utils.DiscriminatorCustomFieldsMappingSerializer"

    def get_name(self):
        part_1 = self.target.registry.name.title()
        part_2 = self.target.base_class.__name__
        name = f"{part_1}{part_2}"

        if self.target.name_prefix:
            name = f"{self.target.name_prefix}{name}"

        return name

    def map_serializer(self, auto_schema, direction):
        mapping = {}

        forced_type = getattr(self.target, "forced_type", None)

        types = (
            self.target.registry.registry.values()
            if not forced_type
            else [self.target.registry.get(forced_type)]
        )

        for type_ in types:
            name = type_.type

            if self.target.name_prefix:
                name = f"{self.target.name_prefix}{name}"

            mapping[name] = type_.get_serializer_class(
                base_class=self.target.base_class,
                request_serializer=self.target.request,
                extra_params=self.target.extra_params,
            )

        return self._map_serializer(auto_schema, direction, mapping)


class PolymorphicMappingSerializerExtensionMixin(
    DiscriminatorCustomFieldsMappingSerializerExtension
):
    """
    Extension to correctly display Polymorphic serializer documentation.
    """

    target_class = "baserow.api.polymorphic.PolymorphicSerializer"
    match_subclasses = True


class PolymorphicRequestMappingSerializerExtensionMixin(
    CustomFieldRegistryMappingSerializerExtension
):
    """
    Extension to correctly display Polymorphic request serializer documentation.
    """

    target_class = "baserow.api.polymorphic.PolymorphicRequestSerializer"
    match_subclasses = True
