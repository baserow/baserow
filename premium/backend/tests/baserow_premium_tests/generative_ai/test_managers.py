from io import BytesIO

import pytest

from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler
from baserow.test_utils.fixtures.generative_ai import (
    TestGenerativeAIWithFilesModelType,
)
from baserow_premium.fields.handler import AIFieldHandler


@pytest.mark.django_db
def test_prepare_file_content(premium_data_fixture, django_assert_num_queries):
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
    ai_files = AIFieldHandler._collect_ai_files(ai_field, row)
    prepared = generative_ai_model_type.prepare_files(ai_files)

    assert len([f for f in prepared if f.content]) == 1
    assert len([f for f in prepared if f.provider_file_id]) == 0
    assert prepared[0].content.data == b"Hello"
    assert prepared[0].content.media_type == "text/plain"


@pytest.mark.django_db
def test_prepare_file_content_skip_files_over_max_size(premium_data_fixture):
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
    # Create a file larger than the 1MB test limit
    large_content = b"x" * (2 * 1024 * 1024)
    user_file_1 = UserFileHandler().upload_user_file(
        user, "aifile.txt", BytesIO(large_content), storage=storage
    )
    table_model = table.get_model()
    values = {f"field_{file_field.id}": [{"name": user_file_1.name}]}
    row = RowHandler().force_create_row(
        user,
        table,
        values,
        table_model,
    )

    ai_files = AIFieldHandler._collect_ai_files(ai_field, row)
    prepared = generative_ai_model_type.prepare_files(ai_files)

    assert len([f for f in prepared if f.content]) == 0
    assert len([f for f in prepared if f.provider_file_id]) == 0
