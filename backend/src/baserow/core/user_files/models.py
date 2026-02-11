import re

from django.contrib.auth import get_user_model
from django.db import models

from .exceptions import InvalidUserFileNameError
from .managers import UserFileQuerySet

User = get_user_model()
deconstruct_user_file_regex = re.compile(r"^([a-zA-Z0-9]+)_([a-zA-Z0-9]+)\.(.*)$")


class UserFile(models.Model):
    original_name = models.CharField(max_length=255)
    original_extension = models.CharField(max_length=64)
    unique = models.CharField(max_length=32, db_index=True)
    size = models.PositiveBigIntegerField()
    mime_type = models.CharField(max_length=127, blank=True)
    is_image = models.BooleanField(default=False)
    image_width = models.PositiveIntegerField(null=True)
    image_height = models.PositiveIntegerField(null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    sha256_hash = models.CharField(max_length=64, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, default=None)

    objects = UserFileQuerySet.as_manager()

    class Meta:
        ordering = ("id",)

    def serialize(self):
        """
        Generates a serialized version that can be stored in other data sources. This
        is possible because the state of the UserFile never changes.

        :return: The serialized version.
        :rtype: dict
        """

        return {
            "name": self.name,
            "size": self.size,
            "mime_type": self.mime_type,
            "is_image": self.is_image,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "uploaded_at": self.uploaded_at.isoformat(),
        }

    @property
    def name(self):
        return f"{self.unique}_{self.sha256_hash}.{self.original_extension}"

    @staticmethod
    def deconstruct_name(name):
        """
        Extracts the model field name values from the provided file name and returns it
        as a mapping.

        :param name: The model generated file name.
        :type name: str
        :return: The field name and extracted value mapping.
        :rtype: dict
        """

        # Note: we match `name` against `deconstruct_user_file_regex` so that
        # we can extract the `unique`, `sha256_hash` and `original_extension`.
        # The `original_extension` may contain unexpected extra characters if it
        # was present in the user's filename. E.g. "jpg-resized" / "jpeg?w=50&h=50".
        matches = deconstruct_user_file_regex.match(name)

        if not matches:
            raise InvalidUserFileNameError(
                name, "The provided name is not in the correct format."
            )

        return {
            "unique": matches[1],
            "sha256_hash": matches[2],
            "original_extension": matches[3],
        }
