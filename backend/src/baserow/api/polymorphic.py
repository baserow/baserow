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

    default_error_messages = {
        "missing_type": "Unable to determine the `type` of the polymorphic data.",
        "invalid_type": '"{type_name}" is not a valid type.',
        "type_mismatch": (
            'The type is fixed to "{default_type_name}" here, so "{type_name}" '
            "cannot be used."
        ),
    }

    def __init__(self, *args, default_type_name: str | None = None, **kwargs):
        # The type to fall back to when the data doesn't name one, and the only
        # type accepted when it does. For use where the caller can't change the
        # type anyway, like the service of a workflow action whose action type
        # pins it.
        self.default_type_name = default_type_name
        super().__init__(*args, **kwargs)

    def fail_on_type_field(self, key, **kwargs):
        """
        Like `fail`, but keys the error under the type field, so the error
        detail stays a dict whether this serializer is nested or standalone.
        """

        try:
            self.fail(key, **kwargs)
        except serializers.ValidationError as e:
            raise serializers.ValidationError({self.type_field_name: e.detail})

    def get_type_from_type_name(self, name):
        return self.registry.get(name)

    def get_type_from_instance(self, instance):
        return self.registry.get_by_model(instance.specific)

    def get_type_from_mapping(self, mapping):
        type_name = (
            mapping.get(self.type_field_name) if isinstance(mapping, dict) else None
        )

        # An absent, `null` or empty `type` all mean the caller didn't name one.
        if type_name is None or type_name == "":
            type_name = self.default_type_name

        if type_name is None:
            self.fail_on_type_field("missing_type")

        # A list or a dict would crash the registry lookup, and other
        # non-string values could still match an instance's `compat_type`, so
        # only a real name is looked up.
        if not isinstance(type_name, str):
            self.fail_on_type_field("invalid_type", type_name=type_name)

        # When the type is pinned, a different one would only pick which
        # serializer the values are checked against, and whatever it accepted
        # would then be dropped without a word. Refused so the caller hears it.
        if self.default_type_name is not None and type_name != self.default_type_name:
            self.fail_on_type_field(
                "type_mismatch",
                type_name=type_name,
                default_type_name=self.default_type_name,
            )

        # An unknown type propagates the registry's own does-not-exist
        # exception, which views map to their specific API errors.
        return self.registry.get(type_name)

    def _get_response_serializer_for_type(self, instance_type):
        """
        Returns the response serializer for the given type. Generating the serializer
        class and building its fields is expensive, so the serializer is created once
        per type and reused for every instance serialized through this serializer,
        for example when it's used with `many=True`. It's memoized on `self` because
        the serializer depends on the context of this instance.
        """

        try:
            serializers_by_type = self._response_serializer_by_type
        except AttributeError:
            serializers_by_type = self._response_serializer_by_type = {}

        if instance_type.type not in serializers_by_type:
            serializer_class = instance_type.get_serializer_class(
                base_class=self.base_class,
                request_serializer=self.request,
                extra_params=self.extra_params,
            )
            serializers_by_type[instance_type.type] = serializer_class(
                instance_type.model_class, context=self.context
            )

        return serializers_by_type[instance_type.type]

    def to_representation(self, instance):
        if not self.required and not instance:
            return None

        if isinstance(instance, dict):
            instance_type = self.get_type_from_mapping(instance)
        else:
            instance = instance.specific
            instance_type = self.get_type_from_instance(instance)

        serializer = self._get_response_serializer_for_type(instance_type)

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
