import contextlib
import typing
from abc import ABC, abstractmethod
from functools import lru_cache
from types import FunctionType
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypedDict,
    TypeVar,
    Union,
    ValuesView,
)
from zipfile import ZipFile

from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import Storage
from django.db import models

from rest_framework import serializers
from rest_framework.serializers import Serializer

from baserow.api.utils import (
    ExceptionMappingType,
    generate_meta_ref_name_based_on_model,
    get_serializer_class,
    map_exceptions,
)
from baserow.core.storage import ExportZipFile

from .exceptions import InstanceTypeAlreadyRegistered, InstanceTypeDoesNotExist
from .formula import BaserowFormulaObject

if typing.TYPE_CHECKING:
    from django.contrib.contenttypes.models import ContentType


class Instance(object):
    """
    This abstract class represents a custom instance that can be added to the registry.
    It must be extended so properties and methods can be added.
    """

    type: str
    """A unique string that identifies the instance."""

    compat_type: str = ""
    """ If this instance has been renamed, and we want to support
        compatibility of the original `type`, implement it with `compat_type`. """

    def __init__(self):
        if not self.type:
            raise ImproperlyConfigured("The type of an instance must be set.")

    def after_register(self):
        """
        Hook that is called after an instance is registered in a registry.
        """

    def before_unregister(self):
        """
        Hook that is called before an instance is unregistered from a registry.
        """


DjangoModel = TypeVar("DjangoModel", bound=models.Model)


class ModelInstanceMixin(Generic[DjangoModel]):
    """
    This mixin introduces a model_class that will be related to the instance. It is to
    be used in combination with a registry that extends the ModelRegistryMixin.
    """

    model_class: Type[DjangoModel]

    def __init__(self):
        if not self.model_class:
            raise ImproperlyConfigured("The model_class of an instance must be set.")

    def get_content_type(self) -> "ContentType":
        """
        Returns the content_type related to the model_class.
        """

        from django.contrib.contenttypes.models import ContentType

        return ContentType.objects.get_for_model(self.model_class)

    def get_object_for_this_type(self, **kwargs) -> DjangoModel:
        """
        Returns the object given the filters in parameter.
        """

        return self.get_content_type().get_object_for_this_type(**kwargs)

    def get_all_objects_for_this_type(self, **kwargs) -> models.QuerySet[DjangoModel]:
        """
        Returns a queryset to get the objects given the filters in parameter.
        """

        return self.get_content_type().get_all_objects_for_this_type(**kwargs)


class CustomFieldsInstanceMixin:
    """
    If an instance can have custom fields per type, they can be defined here.
    """

    allowed_fields = []
    """The field names that are allowed to set when creating and updating"""

    serializer_field_names = []
    """The field names that must be added to the serializer."""

    request_serializer_field_names = None
    """
    The field names that must be added to the request serializer if different from
    the `serializer_field_names`.
    """

    serializer_field_overrides = {}
    """The fields that must be added to the serializer."""

    request_serializer_field_overrides = None
    """
    The fields that must be added to the request serializer if different from the
    `serializer_field_overrides` property.
    """

    serializer_mixins = []
    """
    The serializer mixins that must be added to the serializer. This property is
    useful if you want to add some custom SerializerMethodField for example.
    """

    request_serializer_mixins = None
    """
    The serializer mixins that must be added to the serializer for requests.
    This property is useful if you want to add some custom behaviour for example.
    """

    serializer_field_extra_kwargs = None
    """
    The extra kwargs that must be added to the serializer fields. This property is
    useful if you want to add some custom `write_only` attribute to a field for example.
    """

    serializer_extra_args = []
    """
    A list of extra args that can be passed to the serializer. This is useful if
    you want to add some custom behaviour, like limiting the number of items returned by
    a link row field, for example.
    """

    def __init__(self):
        """
        :raises ValueError: If the object does not have a `model_class` attribute.
        """

        model_class = getattr(self, "model_class")
        if not model_class:
            raise ValueError(
                "Attribute model_class must be set, maybe you forgot to "
                "extend the ModelInstanceMixin?"
            )

    def get_serializer_class(
        self,
        *args,
        request_serializer: bool = False,
        meta_ref_name=None,
        base_class: Serializer = None,
        extra_params=None,
        **kwargs,
    ) -> serializers.ModelSerializer:
        """
        Returns a model serializer class based on this type field names and overrides.

        :raises ValueError: If the object does not have a `model_class` attribute.
        :return: The generated model serializer class.
        """

        if extra_params is None:
            extra_params = {}

        field_overrides = self.get_field_overrides(
            request_serializer, extra_params, **kwargs
        )
        field_names = self.get_field_names(request_serializer, extra_params, **kwargs)

        if meta_ref_name is None:
            meta_ref_name = self.get_meta_ref_name(
                request_serializer, extra_params, **kwargs
            )

        # Build a list of serializers, using two methods:
        # 1) Serializers can provide a function (note: we can't test with callable()
        #    as serializers are callable) which lazy loads a serializer mixin, or
        # 2) Serializers can provide a serializer mixin directly.
        dynamic_serializer_mixins = []
        for serializer_mixin in self.get_serializer_mixins(
            request_serializer, extra_params, **kwargs
        ):
            if isinstance(serializer_mixin, FunctionType):
                dynamic_serializer_mixins.append(serializer_mixin())
            else:
                dynamic_serializer_mixins.append(serializer_mixin)

        return get_serializer_class(
            self.model_class,
            field_names,
            field_overrides=field_overrides,
            base_mixins=dynamic_serializer_mixins,
            meta_extra_kwargs=self.serializer_field_extra_kwargs,
            meta_ref_name=meta_ref_name,
            base_class=base_class,
            *args,
            **kwargs,
        )

    def get_serializer(
        self,
        model_instance_or_instances: Union[models.Model, List[models.Model]],
        base_class: Optional[serializers.ModelSerializer] = None,
        context: Optional[Dict[str, Any]] = None,
        request: bool = False,
        extra_params=None,
        **kwargs: Dict[str, Any],
    ) -> serializers.ModelSerializer:
        """
        Returns an instantiated model serializer based on this type field names and
        overrides. The provided model instance will be used instantiate the serializer.

        :param model_instance_or_instances: The instance or a list of instances for
            which the serializer must be generated.
        :param base_class: The base serializer class that must be extended. For example
            common fields could be stored here.
        :param context: Extra context arguments to pass to the serializers context.
        :param request: True if you want the request serializer.
        :param extra_params: Any additional params that should be passed to the method.
        :param kwargs: The kwargs are used to initialize the serializer class.
        :return: The instantiated generated model serializer.
        """

        if context is None:
            context = {}

        if isinstance(model_instance_or_instances, list):
            model_instance_or_instances = [
                m.specific for m in model_instance_or_instances
            ]
        else:
            model_instance_or_instances = model_instance_or_instances.specific

        serializer_class = self.get_serializer_class(
            base_class=base_class,
            request_serializer=request,
            extra_params=extra_params,
        )

        return serializer_class(model_instance_or_instances, context=context, **kwargs)

    def get_serializer_mixins(
        self, request_serializer: bool, extra_params: Dict, **kwargs
    ) -> List:
        if request_serializer and self.request_serializer_mixins is not None:
            return self.request_serializer_mixins
        else:
            return self.serializer_mixins

    def get_field_overrides(
        self, request_serializer: bool, extra_params: Dict, **kwargs
    ) -> Dict:
        if request_serializer and self.request_serializer_field_overrides is not None:
            return self.request_serializer_field_overrides
        else:
            return self.serializer_field_overrides

    def get_field_names(
        self, request_serializer: bool, extra_params: Dict, **kwargs
    ) -> List[str]:
        if request_serializer and self.request_serializer_field_names is not None:
            return self.request_serializer_field_names
        else:
            return self.serializer_field_names

    def get_meta_ref_name(
        self, request_serializer: bool, extra_params: Dict, **kwargs
    ) -> Optional[str]:
        if request_serializer is None:
            return "Request" + generate_meta_ref_name_based_on_model(
                self.model_class, base_class=kwargs.get("base_class")
            )

        return None

    def get_queryset(self):
        """
        Returns the base queryset potentially enhanced by the `.enhance_queryset` method
        for the model of this class. Requires the `ModelInstance` mixin.
        """

        return self.enhance_queryset(self.model_class.objects.all())

    def enhance_queryset(self, queryset):
        """
        A hook to enhance the queryset for this type like adding `select_related`,
        `prefetch_related` or stuff like that. Called by `.get_queryset` to generate
        the base queryset to use for this type.
        """

        return queryset


class PublicCustomFieldsInstanceMixin(CustomFieldsInstanceMixin):
    """
    A mixin for instance with custom fields but some field should remain private
    when used in some APIs.
    """

    public_serializer_field_names = None
    """The field names that must be added to the serializer if it's public."""

    public_request_serializer_field_names = None
    """
    The field names that must be added to the public request serializer if different
    from the `public_serializer_field_names`.
    """

    request_serializer_field_overrides = None
    """
    The fields that must be added to the request serializer if different from the
    `serializer_field_overrides` property.
    """

    public_serializer_field_overrides = None
    """The fields that must be added to the public serializer."""

    public_request_serializer_field_overrides = None
    """
    The fields that must be added to the public request serializer if different from the
    `public_serializer_field_overrides` property.
    """

    public_serializer_mixins = None
    """
    The serializer mixins that must be added to the public serializer. This property is
    useful if you want to add some custom SerializerMethodField for example.
    """

    public_request_serializer_mixins = None
    """
    The serializer mixins that must be added to the public serializer for requests.
    This property is useful if you want to add some custom behaviour for example.
    """

    def get_serializer_mixins(
        self, request_serializer: bool, extra_params=None, **kwargs
    ) -> List:
        public = extra_params.get("public", False)

        if public:
            if request_serializer and self.public_request_serializer_mixins is not None:
                return self.public_request_serializer_mixins
            if self.public_serializer_mixins is not None:
                return self.public_serializer_mixins

        return super().get_serializer_mixins(request_serializer, extra_params, **kwargs)

    def get_field_overrides(
        self, request_serializer: bool, extra_params=None, **kwargs
    ) -> Dict:
        public = extra_params.get("public", False)

        if public:
            if (
                request_serializer
                and self.public_request_serializer_field_overrides is not None
            ):
                return self.public_request_serializer_field_overrides
            if self.public_serializer_field_overrides is not None:
                return self.public_serializer_field_overrides

        return super().get_field_overrides(request_serializer, extra_params, **kwargs)

    def get_field_names(
        self, request_serializer: bool, extra_params=None, **kwargs
    ) -> List[str]:
        public = extra_params.get("public", False)

        if public:
            if (
                request_serializer
                and self.public_request_serializer_field_names is not None
            ):
                return self.public_request_serializer_field_names
            if self.public_serializer_field_names is not None:
                return self.public_serializer_field_names

        return super().get_field_names(request_serializer, extra_params, **kwargs)

    def get_meta_ref_name(
        self,
        request_serializer: bool,
        extra_params=None,
        **kwargs,
    ) -> Optional[str]:
        meta_ref_name = super().get_meta_ref_name(
            request_serializer, extra_params, **kwargs
        )

        public = extra_params.get("public", False)

        if public:
            meta_ref_name = f"Public{meta_ref_name}"

        return meta_ref_name


class APIUrlsInstanceMixin:
    def get_api_urls(self) -> List:
        """
        If needed custom api related urls to the instance can be added here.

        Example:

            from django.urls import include, path

            def get_api_urls(self):
                from . import api_urls

                return [
                    path('some-url/', include(api_urls, namespace=self.type)),
                ]

            # api_urls.py
            from django.urls import re_path

            urlpatterns = [
                url(r'some-view^$', SomeView.as_view(), name='some_view'),
            ]

        :return: A list containing the urls.
        """

        return []


class MapAPIExceptionsInstanceMixin:
    """
    Example:
        class ExampleInstance(MapAPIExceptionsInstanceMixin, Instance):
            type = 'example'
            api_exceptions_map = {
                SomeSpecificException: 'API_ERROR'
            }

        # If the exception is raised while inside the with map_api_exceptions() the
        # following HTTP response can be expected.

        instance = ExampleInstance()
        with instance.map_api_exceptions():
            raise SomeSpecificException('Reason')

        HTTP/1.1 400
        {
            "error": "API_ERROR",
            "detail": ""
        }
    """

    api_exceptions_map: ExceptionMappingType = {}

    @contextlib.contextmanager
    def map_api_exceptions(self):
        """
        The map_api_exceptions method can be used to map uncaught exceptions to
        certain api error responses. These API exceptions should be defined in the
        api_exceptions_map.
        """

        with map_exceptions(self.api_exceptions_map):
            yield


T = TypeVar("T")


class ImportExportMixin(Generic[T], ABC):
    @abstractmethod
    def export_serialized(self, instance: T) -> Dict[str, Any]:
        """
        Should return with a serialized version of the provided instance. It must be
        JSON serializable and it must be possible to the import via the
        `import_serialized` method.

        :param instance: The instance that must be serialized and exported. Could be
            any object type because it depends on the type instance that uses this
            mixin.
        :return: Serialized version of the instance.
        """

    @abstractmethod
    def import_serialized(
        self, parent: Any, serialized_values: Dict[str, Any], id_mapping: Dict
    ) -> T:
        """
        Should import and create the correct instances in the database based on the
        serialized values exported by the `export_serialized` method. It should create
        a copy. An entry to the mapping could be made if a new instance is created.

        :param parent: Optionally a parent instance can be provided here.
        :param serialized_values: The values that must be inserted.
        :param id_mapping: The map of exported ids to newly created ids that must be
            updated when a new instance has been created.
        :return: The newly created instance.
        """


InstanceSubClass = TypeVar("InstanceSubClass", bound=Instance)


class EasyImportExportMixin(Generic[T], ABC):
    """
    Mixin to automate the export/import process for django models.
    """

    # Describe the properties to serialize
    SerializedDict: Type[TypedDict]

    # List of fields that are potentially sensitive and shouldn't be included
    # when exporting the application.
    sensitive_fields: List[str] = []

    # The parent property name for the model
    parent_property_name: str

    # The name of the id mapping used for import process. Let it None if you don't need
    # this feature.
    id_mapping_name: Optional[str] = None

    # The model class to create
    model_class: Type[T]

    def serialize_property(
        self,
        instance: T,
        prop_name: str,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, any]] = None,
    ) -> Any:
        """
        You can customize the behavior of the serialization of a property with this
        hook.

        :param instance: the instance to serialize.
        :param prop_name: the prop name to serialize.
        :return: the serialized version of for the given prop_name
        """

        if prop_name == "type":
            return self.type

        return getattr(instance, prop_name)

    def get_property_names(self):
        """
        Returns a list of properties to export/import for this type. By default it uses
        the SerializedDict properties.

        :returns: a list of property names belonging to instances of this type.
        """

        return self.SerializedDict.__annotations__.keys()

    def export_serialized(
        self,
        instance: T,
        import_export_config: Optional[Any] = None,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, any]] = None,
    ) -> Dict[str, Any]:
        """
        Exports the instance to a serialized dict that can be imported by the
        `import_serialized` method. This dict is also JSON serializable.

        :param instance: The instance that must be serialized.
        :param files_zip: The zip file where the files must be stored.
        :param storage: The storage where the files must be stored.
        :param cache: The cache instance that is used to cache the files.
        :return: The exported instance as serialized dict.
        """

        exclude_sensitive_data = getattr(
            import_export_config, "exclude_sensitive_data", False
        )

        serialized = {
            key: (
                None
                if exclude_sensitive_data and key in self.sensitive_fields
                else self.serialize_property(
                    instance, key, files_zip=files_zip, storage=storage, cache=cache
                )
            )
            for key in self.get_property_names()
        }

        return serialized

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, any]] = None,
        **kwargs,
    ) -> Any:
        """
        This hooks allow to customize the deserialization of a property.

        :param prop_name: the name of the property being transformed.
        :param value: the value of this property.
        :param id_mapping: the id mapping dict.
        :param kwargs: extra parameters used to deserialize a property.
        :return: the deserialized version for this property.
        """

        return value

    def create_instance_from_serialized(
        self,
        serialized_values: Dict[str, Any],
        id_mapping,
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, any]] = None,
        **kwargs,
    ) -> T:
        """
        Create the instance related to the given serialized values.
        Allow to hook into instance creation while still having the serialized values.

        :param serialized_values: the deserialized values.
        :return: the created instance.
        """

        instance = self.model_class(**serialized_values)
        instance.save()

        return instance

    def import_serialized(
        self,
        parent: Any,
        serialized_values: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, any]] = None,
        **kwargs,
    ) -> T:
        """
        Imports the previously exported dict generated by the `export_serialized`
        method.

        An id_mapping for this class is populated during the process.

        :param parent: The parent object of the to be imported values.
        :param serialized_values: The dict containing the serialized values.
        :param id_mapping: Used to mapped object ids from export to newly created
          instances.
        :param files_zip: The zip file containing the files.
        :param storage: The storage instance that is used to store the files.
        :param cache: The cache instance that is used to cache the files.
        :return: The created instance.
        """

        if self.id_mapping_name and self.id_mapping_name not in id_mapping:
            id_mapping[self.id_mapping_name] = {}

        deserialized_properties = {}
        for name in self.get_property_names():
            if name in serialized_values and name != f"{self.parent_property_name}_id":
                deserialized_properties[name] = self.deserialize_property(
                    name,
                    serialized_values[name],
                    id_mapping,
                    files_zip=files_zip,
                    storage=storage,
                    cache=cache,
                    **kwargs,
                )

        # Remove id key
        original_instance_id = deserialized_properties.pop("id", 0)

        # Remove type if any
        if "type" in deserialized_properties:
            deserialized_properties.pop("type")

        # Add the parent
        deserialized_properties[self.parent_property_name] = parent

        created_instance = self.create_instance_from_serialized(
            deserialized_properties,
            id_mapping=id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        if self.id_mapping_name:
            # Add the created instance to the mapping
            id_mapping[self.id_mapping_name][original_instance_id] = created_instance.id

        return created_instance


class Registry(Generic[InstanceSubClass]):
    name: str
    """The unique name that is used when raising exceptions."""

    does_not_exist_exception_class = InstanceTypeDoesNotExist
    """The exception that is raised when an instance doesn't exist."""

    already_registered_exception_class = InstanceTypeAlreadyRegistered
    """The exception that is raised when an instance is already registered."""

    def __init__(self):
        if not getattr(self, "name", None):
            raise ImproperlyConfigured(
                "The name must be set on an "
                "InstanceModelRegistry to raise proper errors."
            )

        self.registry: Dict[str, InstanceSubClass] = {}

    def get(self, type_name: str) -> InstanceSubClass:
        """
        Returns a registered instance of the given type name.

        :param type_name: The unique name of the registered instance.
        :type type_name: str
        :raises InstanceTypeDoesNotExist: If the instance with the provided `type_name`
            does not exist in the registry.
        :return: The requested instance.
        :rtype: InstanceModelInstance
        """

        # If the `type_name` isn't in the registry, we may raise DoesNotExist.
        if type_name not in self.registry:
            # But first, we'll test to see if it matches an Instance's
            # `compat_name`. If it does, we'll use that Instance's `type`.
            type_name_via_compat = self.get_by_type_name_by_compat(type_name)
            if type_name_via_compat:
                type_name = type_name_via_compat
            else:
                raise self.does_not_exist_exception_class(
                    type_name, f"The {self.name} type {type_name} does not exist."
                )

        return self.registry[type_name]

    def get_by_type_name_by_compat(self, compat_name: str) -> Optional[str]:
        """
        Returns a registered instance's `type` by using the compatibility name.
        """

        for instance in self.get_all():
            if instance.compat_type == compat_name:
                return instance.type

    def get_by_type(self, instance_type: Type[InstanceSubClass]) -> InstanceSubClass:
        return self.get(instance_type.type)

    def get_all(self) -> ValuesView[InstanceSubClass]:
        """
        Returns all registered instances

        :return: A list of the registered instances.
        :rtype: List[InstanceModelInstance]
        """

        return self.registry.values()

    def get_types(self) -> List[str]:
        """
        Returns a list of available type names.

        :return: The list of available types.
        :rtype: List
        """

        return list(self.registry.keys())

    def get_types_as_tuples(self) -> List[Tuple[str, str]]:
        """
        Returns a list of available type names.

        :return: The list of available types.
        :rtype: List[Tuple[str,str]]
        """

        return [(k, k) for k in self.registry.keys()]

    def register(self, instance: InstanceSubClass):
        """
        Registers a new instance in the registry.

        :param instance: The instance that needs to be registered.
        :type instance: Instance
        :raises ValueError: When the provided instance is not an instance of Instance.
        :raises InstanceTypeAlreadyRegistered: When the instance's type has already
            been registered.
        """

        if not isinstance(instance, Instance):
            raise ValueError(f"The {self.name} must be an instance of Instance.")

        if instance.type in self.registry:
            raise self.already_registered_exception_class(
                f"The {self.name} with type {instance.type} is already registered."
            )

        self.registry[instance.type] = instance

        instance.after_register()

    def unregister(self, value: Union[str, InstanceSubClass]):
        """
        Removes a registered instance from the registry. An instance or type name can be
        provided as value.

        :param value: The instance or type name.
        :type value: Instance or str
        :raises ValueError: If the provided value is not an instance of Instance or
            string containing the type name.
        """

        if isinstance(value, Instance):
            for type_name, instance in self.registry.items():
                if instance == value:
                    value = type_name

        if isinstance(value, str):
            instance = self.registry[value]
            instance.before_unregister()
            del self.registry[value]
        else:
            raise ValueError(
                f"The value must either be an {self.name} instance or type name"
            )


class ModelRegistryMixin(Generic[DjangoModel, InstanceSubClass]):
    def get_by_model(
        self, model_instance: Union[DjangoModel, Type[DjangoModel]]
    ) -> InstanceSubClass:
        """
        Returns a registered instance of the given model class.

        :param model_instance: The value that must be a Model class or
            an instance of any model_class.
        :raises InstanceTypeDoesNotExist: When the provided model instance is not
            found in the registry.
        :return: The registered instance.
        """

        if isinstance(model_instance, type):
            clazz = model_instance
        else:
            clazz = model_instance.__class__

        return self.get_for_class(clazz)

    @lru_cache
    def get_for_class(self, clazz: Type[DjangoModel]) -> InstanceSubClass:
        """
        Returns a registered instance of the given model class.

        :param model_instance: The value that must be a Model class.
        :raises InstanceTypeDoesNotExist: When the provided model instance is not
            found in the registry.
        :return: The registered instance.
        """

        most_specific_value = None
        for value in self.registry.values():
            value_model_class = value.model_class
            if value_model_class == clazz or issubclass(clazz, value_model_class):
                if most_specific_value is None:
                    most_specific_value = value
                else:
                    # There might be values where one is a sub type of another. The
                    # one with the longer mro is the more specific type (it inherits
                    # from more base classes)
                    most_specific_num_base_classes = len(
                        most_specific_value.model_class.mro()
                    )
                    value_num_base_classes = len(value_model_class.mro())
                    if value_num_base_classes > most_specific_num_base_classes:
                        most_specific_value = value

        if most_specific_value is not None:
            return most_specific_value

        raise self.does_not_exist_exception_class(
            f"The {self.name} model {clazz} does not exist."
        )

    def get_all_by_model_isinstance(
        self, model_instance: DjangoModel
    ) -> List[InstanceSubClass]:
        """
        Returns all registered types which are an instance of the provided
        model_instance.
        """

        all_matching_non_abstract_types = []
        for value in self.registry.values():
            value_model_class = value.model_class
            if value_model_class == model_instance or isinstance(
                model_instance, value_model_class
            ):
                all_matching_non_abstract_types.append(value)

        return all_matching_non_abstract_types

    def get_model_names(self) -> list[tuple[str, str]]:
        """
        Returns a list of app_name, model_name pairs of models
        available in the registry.
        """

        all_model_names = []
        for value in self.registry.values():
            model_name = (
                value.model_class._meta.app_label,
                value.model_class._meta.model_name,
            )
            all_model_names.append(model_name)
        return all_model_names


class CustomFieldsRegistryMixin(Generic[DjangoModel]):
    def get_serializer(
        self,
        model_instance_or_instances: Union[DjangoModel, List[DjangoModel]],
        base_class: Optional[Type[serializers.ModelSerializer]] = None,
        context: Optional[Dict[str, any]] = None,
        extra_params=None,
        **kwargs,
    ):
        """
        Based on the provided model_instance and base_class a unique serializer
        containing the correct field type is generated.

        :param model_instance_or_instances: The instance or list of instances for which
            the serializer must be generated.
        :type model_instance_or_instances: Model
        :param base_class: The base serializer class that must be extended. For example
            common fields could be stored here.
        :type base_class: ModelSerializer
        :param context: Extra context arguments to pass to the serializers context.
        :type kwargs: dict
        :param extra_params: Any additional params that should be passed to the method.
        :param kwargs: The kwargs are used to initialize the serializer class.
        :type kwargs: dict
        :raises ValueError: When the `get_by_model` method was not found, which could
            indicate the `ModelRegistryMixin` has not been mixed in.
        :return: The instantiated generated model serializer.
        :rtype: ModelSerializer
        """

        get_by_model = getattr(self, "get_by_model")
        if not get_by_model:
            raise ValueError(
                "The method get_by_model must exist on the registry in "
                "order to generate the serializer, maybe you forgot to "
                "extend the ModelRegistryMixin?"
            )
        if isinstance(model_instance_or_instances, list):
            instance_type = self.get_by_model(
                model_instance_or_instances[0].specific_class
            )
        else:
            instance_type = self.get_by_model(
                model_instance_or_instances.specific_class
            )
        return instance_type.get_serializer(
            model_instance_or_instances,
            base_class=base_class,
            context=context,
            extra_params=extra_params,
            **kwargs,
        )


class APIUrlsRegistryMixin:
    @property
    def api_urls(self):
        """
        Returns a list of all the api urls that are in the registered instances.

        :return: The api urls of the registered instances.
        :rtype: list
        """

        api_urls = []
        for types in self.registry.values():
            api_urls += types.get_api_urls()
        return api_urls


class InstanceWithFormulaMixin:
    """
    This mixin provides the formula_generator(), which is a generator that
    iterates through a given Instance's formulas.
    """

    simple_formula_fields: List[str] = []

    def formula_generator(
        self, instance: Instance
    ) -> Generator[str | Instance, str, None]:
        """
        Return a generator that iterates over all formula fields of an Instance.
        The yielded value will be a formula string.

        If the generator is provided a new formula via the `send()` method, it
        will be used to update (but not save) the instance's formula field.
        When `send()` is called, the generator will yield the instance rather
        than the formula string.

        Since changes to the instance are not saved, the caller should check
        if the formula has changed, and save the instance if appropriate.
        """

        for formula_field in self.simple_formula_fields:
            formula: BaserowFormulaObject = BaserowFormulaObject.to_formula(
                getattr(instance, formula_field)
            )
            new_formula = yield formula
            if new_formula is not None:
                setattr(instance, formula_field, new_formula)
                yield instance

    def import_formulas(
        self,
        instance: Instance,
        id_mapping: Dict[str, Any],
        import_formula: Callable[[str, Dict[str, Any]], str],
        **kwargs: Dict[str, Any],
    ) -> Set[Instance]:
        """
        Instantiates the formula generator and returns a set of all updated
        models.

        As with the formula_generator(), this method does not save any updates
        made to the instance. Instead, it returns a set of all updated model
        instances. The caller should call `.save()` on the instances to persist
        any new formulas that were updated in the instances.
        """

        updated_models: Set[Instance] = set()
        formula_gen = self.formula_generator(instance)
        for formula in formula_gen:
            new_formula = import_formula(formula, id_mapping, **kwargs)
            if new_formula != formula:
                updated_models.add(formula_gen.send(new_formula))

        return updated_models
