import mimetypes
import pathlib

from django.core.files.base import ContentFile
from django.core.files.storage import Storage

from baserow.core.models import UserFile
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.utils import random_string


class UserFileFixtures:
    def create_user_file(self, **kwargs):
        if "original_name" not in kwargs:
            kwargs["original_name"] = self.fake.file_name()

        if "original_extension" not in kwargs:
            kwargs["original_extension"] = (
                pathlib.Path(kwargs["original_name"]).suffix[1:].lower()
            )

        if "unique" not in kwargs:
            kwargs["unique"] = random_string(32)

        if "size" not in kwargs:
            kwargs["size"] = 100

        if "mime_type" not in kwargs:
            kwargs["mime_type"] = mimetypes.guess_type(kwargs["original_name"])[0] or ""

        if "uploaded_by" not in kwargs:
            kwargs["uploaded_by"] = self.create_user()

        if "sha256_hash" not in kwargs:
            kwargs["sha256_hash"] = random_string(64)

        user_file = UserFile.objects.create(**kwargs)

        return user_file

    def save_content_in_user_file(
        self, user_file: UserFile, storage: Storage, content: str = ""
    ) -> UserFile:
        path = UserFileHandler().user_file_path(user_file.name)
        content = content or f"test file  {user_file.original_name} at {path}"
        storage.save(path, ContentFile(content))
        return user_file
