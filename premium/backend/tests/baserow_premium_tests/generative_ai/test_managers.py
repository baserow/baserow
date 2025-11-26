from io import BytesIO
from unittest.mock import Mock

import pytest
from baserow_premium.generative_ai.managers import AIFileManager

from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler
from baserow.test_utils.fixtures.generative_ai import TestGenerativeAIWithFilesModelType
from baserow.test_utils.helpers import AnyStr


@pytest.mark.django_db
def test_upload_files_from_file_field(premium_data_fixture, django_assert_num_queries):
    storage = get_default_storage()

    user = premium_data_fixture.create_user()
    generative_ai_model_type = TestGenerativeAIWithFilesModelType()
    table = premium_data_fixture.create_database_table()
    file_field = premium_data_fixture.create_file_field(
        table=table, order=0, name="File"
    )
    ai_field = premium_data_fixture.create_ai_field(
        table=table, order=1, name="AI prompt", ai_file_field=file_field
    )
    user_file_1 = UserFileHandler().upload_user_file(
        user, "aifile.txt", BytesIO(b"Hello"), storage=storage
    )
    table_model = table.get_model()

    values = {f"field_{file_field.id}": [{"name": user_file_1.name}]}

    row = RowHandler().force_create_row(
        user,
        table,
        values,
        table_model,
    )

    ai_field.refresh_from_db()
    with django_assert_num_queries(0):
        file_ids = AIFileManager.upload_files_from_file_field(
            ai_field, row, generative_ai_model_type
        )
        assert file_ids == [AnyStr()]

    assert len(generative_ai_model_type._files) == 1
    assert generative_ai_model_type._files[file_ids[0]]["file_name"].endswith(
        f"/baserow/media/user_files/{user_file_1.name}"
    )


@pytest.mark.django_db
def test_upload_files_from_file_field_skip_files_over_max_size(premium_data_fixture):
    storage = get_default_storage()

    user = premium_data_fixture.create_user()
    generative_ai_model_type = TestGenerativeAIWithFilesModelType()
    table = premium_data_fixture.create_database_table()
    file_field = premium_data_fixture.create_file_field(
        table=table, order=0, name="File"
    )
    ai_field = premium_data_fixture.create_ai_field(
        table=table, order=1, name="AI prompt", ai_file_field=file_field
    )
    user_file_1 = UserFileHandler().upload_user_file(
        user, "aifile.txt", BytesIO(b"Hello"), storage=storage
    )
    table_model = table.get_model()
    values = {f"field_{file_field.id}": [{"name": user_file_1.name}]}
    row = RowHandler().force_create_row(
        user,
        table,
        values,
        table_model,
    )
    generative_ai_model_type.get_max_file_size = Mock()
    generative_ai_model_type.get_max_file_size.return_value = 0
    AIFileManager.upload_files_from_file_field(ai_field, row, generative_ai_model_type)

    stored_files = getattr(generative_ai_model_type, "_files", {})
    assert len(stored_files) == 0
