from django.conf import settings

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.core.models import UserFile
from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler


class UserFileUploadViaURLRequestSerializer(serializers.Serializer):
    url = serializers.URLField()


class UserFileURLAndThumbnailsSerializerMixin(serializers.Serializer):
    url = serializers.SerializerMethodField()
    thumbnails = serializers.SerializerMethodField()

    def get_instance_attr(self, instance, name):
        return getattr(instance, name)

    @extend_schema_field(OpenApiTypes.URI)
    def get_url(self, instance):
        storage = get_default_storage()
        name = self.get_instance_attr(instance, "name")
        path = UserFileHandler().user_file_path(name)
        url = storage.url(path)
        return url

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_thumbnails(self, instance):
        if not self.get_instance_attr(instance, "is_image"):
            return None

        name = self.get_instance_attr(instance, "name")
        storage = get_default_storage()

        return {
            thumbnail_name: {
                "url": storage.url(
                    UserFileHandler().user_file_thumbnail_path(name, thumbnail_name)
                ),
                "width": size[0],
                "height": size[1],
            }
            for thumbnail_name, size in settings.USER_THUMBNAILS.items()
        }


class UserFileSerializer(
    UserFileURLAndThumbnailsSerializerMixin, serializers.ModelSerializer
):
    name = serializers.SerializerMethodField()

    class Meta:
        model = UserFile
        fields = (
            "size",
            "mime_type",
            "is_image",
            "image_width",
            "image_height",
            "uploaded_at",
            "url",
            "thumbnails",
            "name",
            "original_name",
        )

    @extend_schema_field(OpenApiTypes.STR)
    def get_name(self, instance):
        return instance.name


@extend_schema_field(UserFileSerializer)
class UserFileField(serializers.Field):
    """
    This field can be used for validating user provided user files, which means a
    user has provided a dict containing the user file name. It will check if that
    user file exists and returns that instance. Vice versa, a user file instance will
    be serialized when converted to data by the serializer.

    Example:
    Serializer(data={
        "user_file": {"name": "filename.jpg"}
    }).data == {"user_file": UserFile(...)}

    The field can also be used for serializing a user file. The value must then be
    provided as instance to the serializer.

    Example:
    Serializer({
        "user_file": UserFile(...)
    }).data == {"user_file": {"name": "filename.jpg", ...}}
    """

    default_error_messages = {
        "invalid_value": "The value must be an object containing the file name.",
        "invalid_user_file": "The provided user file does not exist.",
    }

    def __init__(self, *args, **kwargs):
        allow_null = kwargs.pop("allow_null", True)
        default = kwargs.pop("default", None)
        super().__init__(allow_null=allow_null, default=default, *args, **kwargs)

    def to_internal_value(self, data):
        if isinstance(data, UserFile):
            return data

        if not isinstance(data, dict) or not isinstance(data.get("name"), str):
            self.fail("invalid_value")

        try:
            user_file = UserFile.objects.all().name(data["name"]).get()
        except UserFile.DoesNotExist:
            self.fail("invalid_user_file")

        return user_file

    def to_representation(self, value):
        if isinstance(value, UserFile) and self.parent.instance is not None:
            return UserFileSerializer(value).data
        return value
