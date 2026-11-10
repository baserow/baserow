from django.core.files.base import ContentFile

import pytest

from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.user_templates.file_transfer import TemplateFilesTransfer


def test_add_reads_no_bytes():
    transfer = TemplateFilesTransfer(get_default_storage())
    read = []

    def chunks():
        read.append(True)
        yield b"content"

    transfer.add(chunks(), "first.txt")
    transfer.add(chunks(), "second.txt")
    transfer.add(chunks(), "first.txt")

    assert read == []
    assert transfer.info_list() == [{"name": "first.txt"}, {"name": "second.txt"}]


@pytest.mark.django_db
def test_open_raises_key_error_for_a_name_that_is_not_there(
    data_fixture, use_tmp_media_root
):
    storage = get_default_storage()
    handler = UserFileHandler()
    stored = handler.upload_user_file(None, "stored.txt", ContentFile(b"Stored"))
    gone = handler.upload_user_file(None, "gone.txt", ContentFile(b"Gone"))
    transfer = TemplateFilesTransfer(storage)
    transfer.add(iter([]), gone.name)
    storage.delete(handler.user_file_path(gone.name))

    with pytest.raises(KeyError):
        transfer.open(stored.name)
    with pytest.raises(KeyError):
        transfer.open(gone.name)
