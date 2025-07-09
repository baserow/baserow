from typing import Any, Dict

from rest_framework import serializers
from rest_framework.fields import empty


class BasePolymorphicSerializer(serializers.Serializer):
    """
    This class is meant to be used when serializing polymorphic models.
    It creates the related polymorphic DRF serializer.

    For instance if you have a model using our PolymorphicContentTypeMixin class like:

    Example:

        class MyPolymorphicModel(
            PolymorphicContentTypeMixin, models.Model
        ):

            content_type = models.ForeignKey(
                ContentType,
                verbose_name="content type",
                related_name="auth_providers",
                on_delete=models.CASCADE,
            )
            ...

    That is associated with a registry:

        class MyPolymorphicType(
            CustomFieldsInstanceMixin,
            ModelInstanceMixin,
            Instance,
        ):

        class MyPolymorphicTypeRegistry(
            ModelRegistryMixin, Registry
        ):
            ...

        my_polymorphic_type_registry = MyPolymorphicTypeRegistry()


    You can optionally create a base serializer:

        class BaseMyPolymorphicSerializer(serializers.Serializer):
            ...

    and finally create the polymorphic serializer:

        class MyPolymorphicSerializer(PolymorphicSerializer):
            base_class = BaseMyPolymorphicSerializer
            registry = my_polymorphic_type_registry

    and Voilà, you have a serializer that reads the type of your instance to use the
    right serializer and moreover this is correctly documented in Redoc when you use it.

    You can use it in other `serializer_field_overrides` for instance, which is a common
    use case when you have a polymorphic type that references another polymorphic type.
    """

    # The base serializer used to generate the serializer for the model.
    base_class: serializers.Serializer = serializers.Serializer

    # The name of the type property to use to get the type
    type_field_name: str = "type"

    # The polymorphic registry for the model
    registry: Any

    # Whether it's a request serializer
    request: bool = False

    # If you need a name prefix to avoid collision in Redoc
    name_prefix: str | None = None

    # A type name you want to preselect for Redoc
    force_type: str | None = None

    # Used for instance for creating public serializers
    extra_params: Dict[str, Any] = None

    def get_type_from_type_name(self, name):
        return self.registry.get(name)

    def get_type_from_instance(self, instance):
        return self.registry.get_by_model(instance.specific)

    def get_type_from_mapping(self, mapping):
        if self.type_field_name in mapping:
            return self.registry.get(mapping[self.type_field_name])
        else:
            self.fail("Unable to determine the `type` of the polymorphic data.")

    def to_representation(self, instance):
        if not self.required and not instance:
            return None

        if isinstance(instance, dict):
            instance_type = self.get_type_from_mapping(instance)
        else:
            instance = instance.specific
            instance_type = self.get_type_from_instance(instance)

        serializer = instance_type.get_serializer(
            instance_type.model_class,
            base_class=self.base_class,
            request=self.request,
            context=self.context,
            extra_params=self.extra_params,
        )

        ret = serializer.to_representation(instance)
        ret[self.type_field_name] = instance_type.type

        return ret

    def to_internal_value(self, data):
        if self.partial and self.instance:
            instance_type = self.get_type_from_instance(self.instance)
        else:
            instance_type = self.get_type_from_mapping(data)

        serializer = instance_type.get_serializer(
            instance_type.model_class,
            base_class=self.base_class,
            request=self.request,
            context=self.context,
            extra_params=self.extra_params,
        )

        return serializer.to_internal_value(data)

    def create(self, validated_data):
        type_name = validated_data.pop(self.type_field_name)
        instance_type = self.get_type_from_type_name(type_name)
        serializer = instance_type.get_serializer(
            instance_type.model_class,
            base_class=self.base_class,
            request=self.request,
            context=self.context,
            extra_params=self.extra_params,
        )

        return serializer.create(validated_data)

    def update(self, instance, validated_data):
        if self.type_field_name in validated_data:
            type_name = validated_data.pop(self.type_field_name)
            instance_type = self.get_type_from_type_name(type_name)
        else:
            instance_type = self.get_type_from_instance(instance)

        serializer = instance_type.get_serializer(
            instance_type.model_class,
            base_class=self.base_class,
            request=self.request,
            context=self.context,
            extra_params=self.extra_params,
        )

        return serializer.update(instance, validated_data)

    def is_valid(self, *args, **kwargs):
        valid = super().is_valid(*args, **kwargs)

        try:
            if self.partial and self.instance:
                instance_type = self.get_type_from_instance(self.instance)
            else:
                instance_type = self.get_type_from_mapping(self.initial_data)

            serializer = instance_type.get_serializer(
                instance_type.model_class,
                base_class=self.base_class,
                request=self.request,
                context=self.context,
                data=self.data,
                partial=self.partial,
                extra_params=self.extra_params,
            )
        except serializers.ValidationError:
            child_valid = False
        else:
            child_valid = serializer.is_valid(*args, **kwargs)
            self._errors.update(serializer.errors)

        return valid and child_valid

    def run_validation(self, data=empty):
        if not self.required and data == empty:
            return {}

        if self.partial and self.instance:
            instance_type = self.get_type_from_instance(self.instance)
        else:
            instance_type = self.get_type_from_mapping(data)

        serializer = instance_type.get_serializer(
            instance_type.model_class,
            base_class=self.base_class,
            request=self.request,
            context=self.context,
            partial=self.partial,
            extra_params=self.extra_params,
        )

        validated_data = serializer.run_validation(data)
        validated_data[self.type_field_name] = instance_type.type

        return validated_data


class PolymorphicSerializer(BasePolymorphicSerializer):
    """
    Class used to generate the right redoc documentation.
    """


class PolymorphicRequestSerializer(BasePolymorphicSerializer):
    """
    Class used to generate the right redoc documentation.
    """

    request = True
