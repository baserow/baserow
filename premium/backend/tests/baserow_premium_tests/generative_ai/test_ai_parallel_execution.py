from io import BytesIO

import pytest
from baserow_premium.fields.job_types import AIValueGenerator

from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.generative_ai.exceptions import GenerativeAIPromptError
from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.utils import Progress


@pytest.mark.django_db
def test_ai_parallel_execution(premium_data_fixture):
    storage = get_default_storage()

    user = premium_data_fixture.create_user()
    premium_data_fixture.create_premium_license_user(user=user)
    workspace = premium_data_fixture.create_workspace(user=user)
    database = premium_data_fixture.create_database_application(
        user=user, workspace=workspace
    )
    table = premium_data_fixture.create_database_table(database=database)
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

    values = [
        {f"field_{file_field.id}": [{"name": user_file_1.name}]},
        {f"field_{file_field.id}": [{"name": user_file_1.name}]},
        {f"field_{file_field.id}": [{"name": user_file_1.name}]},
    ] * 10

    RowHandler().force_create_rows(
        user,
        table,
        values,
        model=table_model,
        send_realtime_update=False,
        send_webhook_events=False,
    )

    rows = table_model.objects.all()

    progress = Progress(len(rows))
    gen = AIValueGenerator(
        user=user,
        ai_field=ai_field,
        progress=progress,
    )
    gen.process(rows.order_by("id"))

    assert len(rows) == 30
    assert gen.finished == len(rows)
    assert not gen.has_errors
    assert progress.progress == 30


@pytest.mark.django_db
def test_ai_parallel_execution_with_error(premium_data_fixture):
    storage = get_default_storage()
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    premium_data_fixture.create_premium_license_user(user=user)

    workspace = premium_data_fixture.create_workspace(user=user)
    database = premium_data_fixture.create_database_application(
        user=user, workspace=workspace
    )
    table = premium_data_fixture.create_database_table(database=database)
    file_field = premium_data_fixture.create_file_field(
        table=table, order=0, name="File"
    )
    ai_field = premium_data_fixture.create_ai_field(
        table=table,
        order=1,
        name="AI prompt",
        ai_file_field=file_field,
        ai_generative_ai_type="test_generative_ai_prompt_error",
        ai_generative_ai_model="test_1",
    )
    user_file_1 = UserFileHandler().upload_user_file(
        user, "aifile.txt", BytesIO(b"Hello"), storage=storage
    )
    table_model = table.get_model()

    values = [
        {f"field_{file_field.id}": [{"name": user_file_1.name}]},
        {f"field_{file_field.id}": [{"name": user_file_1.name}]},
        {f"field_{file_field.id}": [{"name": user_file_1.name}]},
    ] * 10

    RowHandler().force_create_rows(
        user,
        table,
        values,
        model=table_model,
        send_realtime_update=False,
        send_webhook_events=False,
    )

    rows = table_model.objects.all()

    progress = Progress(len(rows))
    gen = AIValueGenerator(
        user=user,
        ai_field=ai_field,
        progress=progress,
    )

    with pytest.raises(GenerativeAIPromptError):
        gen.process(rows.order_by("id"))

    assert len(rows) == 30
    assert gen.finished == 5
    assert gen.has_errors
    assert progress.progress == 5
