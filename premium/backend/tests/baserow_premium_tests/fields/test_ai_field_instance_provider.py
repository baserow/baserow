from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

from django.db import connection
from django.shortcuts import reverse

import pytest
from openai.resources.files import Files
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.openai import OpenAIResponsesModel
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel
from baserow.core.generative_ai.exceptions import ModelDoesNotBelongToType
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.storage import get_default_storage
from baserow_premium.fields.handler import AIFieldHandler
from baserow_premium.fields.job_types import AIValueGenerator
from baserow_premium.fields.models import AIField
from baserow_premium.fields.pydantic_models import BaserowFormulaModel


def create_instance_openai_provider(model_identifier="gpt-instance"):
    provider = AIProviderConfig.objects.create(
        provider_type="openai",
        api_key="instance-api-key",
        extra_settings={"organization": "instance-organization"},
    )
    model = AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier=model_identifier,
    )
    return provider, model


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_can_select_an_instance_provider_model(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    provider, model = create_instance_openai_provider()
    second_model = AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="gpt-instance-2",
    )

    response = api_client.get(
        reverse("api:workspaces:list"),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    workspace = next(
        item for item in response.json() if item["id"] == table.database.workspace_id
    )
    assert workspace["generative_ai_models_enabled"]["openai"] == [
        model.model_identifier,
        second_model.model_identifier,
    ]

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "AI",
            "type": "ai",
            "ai_generative_ai_type": "openai",
            "ai_generative_ai_model": model.model_identifier,
            "ai_prompt": "'Hello'",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["ai_generative_ai_type"] == "openai"
    assert response.json()["ai_generative_ai_model"] == model.model_identifier
    field = AIField.objects.get(id=response.json()["id"])
    assert field.ai_generative_ai_type == "openai"
    assert field.ai_generative_ai_model == model.model_identifier

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field.id}),
        {"ai_generative_ai_model": second_model.model_identifier},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    field.refresh_from_db()
    assert field.ai_generative_ai_type == "openai"
    assert field.ai_generative_ai_model == second_model.model_identifier


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_generation_uses_instance_provider_configuration(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    _, model = create_instance_openai_provider()
    field = FieldHandler().create_field(
        user,
        table,
        "ai",
        name="AI",
        ai_generative_ai_type="openai",
        ai_generative_ai_model=model.model_identifier,
        ai_prompt="'Hello'",
    )
    row = RowHandler().create_row(user, table, {})
    model_type = generative_ai_model_type_registry.get("openai")

    def prompt(model_identifier, prompt, workspace=None, **kwargs):
        assert model_identifier == model.model_identifier
        assert model_type.get_api_key(workspace) == "instance-api-key"
        assert model_type.get_organization(workspace) == "instance-organization"
        assert model_type.get_enabled_models(workspace) == [model.model_identifier]
        assert kwargs["settings_override"]["api_key"] == "instance-api-key"
        return "result"

    with patch.object(model_type, "prompt", side_effect=prompt):
        assert AIFieldHandler.generate_value_with_ai(field, row) == "result"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_formula_generation_uses_instance_provider_configuration(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    _, model = create_instance_openai_provider()
    model_type = generative_ai_model_type_registry.get("openai")

    def prompt(model_identifier, prompt, workspace=None, **kwargs):
        assert model_identifier == model.model_identifier
        assert model_type.get_api_key(workspace) == "instance-api-key"
        return BaserowFormulaModel(formula="field('id')")

    with patch.object(model_type, "prompt", side_effect=prompt):
        result = AIFieldHandler.generate_formula_with_ai(
            table,
            "openai",
            model.model_identifier,
            "Return the row id",
        )

    assert result == "field('id')"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_keeps_workspace_settings_precedence_until_they_are_migrated(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    _, instance_model = create_instance_openai_provider()
    workspace = table.database.workspace
    workspace.generative_ai_models_settings = {
        "openai": {
            "api_key": "workspace-api-key",
            "models": [instance_model.model_identifier],
        }
    }
    workspace.save(update_fields=("generative_ai_models_settings",))

    field = FieldHandler().create_field(
        user,
        table,
        "ai",
        name="AI",
        ai_generative_ai_type="openai",
        ai_generative_ai_model=instance_model.model_identifier,
        ai_prompt="'Hello'",
    )
    row = RowHandler().create_row(user, table, {})
    model_type = generative_ai_model_type_registry.get("openai")

    def prompt(model_identifier, prompt, workspace=None, **kwargs):
        assert model_identifier == instance_model.model_identifier
        assert model_type.get_api_key(workspace) == "workspace-api-key"
        return "workspace-result"

    with patch.object(model_type, "prompt", side_effect=prompt):
        assert AIFieldHandler.generate_value_with_ai(field, row) == "workspace-result"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_uses_workspace_owned_database_provider(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    _, instance_model = create_instance_openai_provider()
    workspace_provider = AIProviderConfig.objects.create(
        workspace=table.database.workspace,
        provider_type="openai",
        api_key="workspace-database-key",
    )
    workspace_model = AIProviderModel.objects.create(
        provider_config=workspace_provider,
        model_identifier="gpt-workspace-database",
    )
    field = FieldHandler().create_field(
        user,
        table,
        "ai",
        name="AI",
        ai_generative_ai_type="openai",
        ai_generative_ai_model=workspace_model.model_identifier,
        ai_prompt="'Hello'",
    )
    row = RowHandler().create_row(user, table, {})
    model_type = generative_ai_model_type_registry.get("openai")

    def prompt(model_identifier, prompt, workspace=None, **kwargs):
        assert model_identifier == workspace_model.model_identifier
        assert model_type.get_api_key(workspace) == "workspace-database-key"
        assert model_type.get_enabled_models(workspace) == [
            workspace_model.model_identifier,
            instance_model.model_identifier,
        ]
        assert kwargs["settings_override"]["api_key"] == "workspace-database-key"
        return "workspace-database-result"

    with patch.object(model_type, "prompt", side_effect=prompt):
        assert AIFieldHandler.generate_value_with_ai(field, row) == (
            "workspace-database-result"
        )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_inherits_an_instance_model_alongside_a_workspace_provider(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    _, instance_model = create_instance_openai_provider()
    workspace_provider = AIProviderConfig.objects.create(
        workspace=table.database.workspace,
        provider_type="openai",
        api_key="workspace-database-key",
    )
    AIProviderModel.objects.create(
        provider_config=workspace_provider,
        model_identifier="gpt-workspace-database",
    )
    field = FieldHandler().create_field(
        user,
        table,
        "ai",
        name="AI",
        ai_generative_ai_type="openai",
        ai_generative_ai_model=instance_model.model_identifier,
        ai_prompt="'Hello'",
    )
    row = RowHandler().create_row(user, table, {})
    model_type = generative_ai_model_type_registry.get("openai")

    def prompt(model_identifier, prompt, workspace=None, **kwargs):
        assert model_identifier == instance_model.model_identifier
        assert kwargs["settings_override"]["api_key"] == "instance-api-key"
        assert kwargs["settings_override"]["organization"] == ("instance-organization")
        return "instance-result"

    with patch.object(model_type, "prompt", side_effect=prompt):
        assert AIFieldHandler.generate_value_with_ai(field, row) == "instance-result"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_keeps_legacy_resolution_without_a_database_provider(
    premium_data_fixture, settings
):
    settings.BASEROW_OPENAI_API_KEY = "environment-api-key"
    settings.BASEROW_OPENAI_MODELS = ["gpt-environment"]
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)

    field = FieldHandler().create_field(
        user,
        table,
        "ai",
        name="AI",
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-environment",
        ai_prompt="'Hello'",
    )
    row = RowHandler().create_row(user, table, {})
    model_type = generative_ai_model_type_registry.get("openai")

    def prompt(model_identifier, prompt, workspace=None, **kwargs):
        assert model_identifier == "gpt-environment"
        assert model_type.get_api_key(workspace) == "environment-api-key"
        return "environment-result"

    with patch.object(model_type, "prompt", side_effect=prompt):
        assert AIFieldHandler.generate_value_with_ai(field, row) == "environment-result"


@pytest.mark.django_db
@pytest.mark.field_ai
@pytest.mark.parametrize("organization", [None, "environment-organization"])
@pytest.mark.parametrize("with_file", [False, True])
def test_environment_ai_field_workers_use_preloaded_provider_state(
    premium_data_fixture, settings, organization, with_file
):
    settings.BASEROW_OPENAI_API_KEY = "environment-api-key"
    settings.BASEROW_OPENAI_MODELS = ["gpt-environment"]
    settings.BASEROW_OPENAI_ORGANIZATION = organization
    settings.BASEROW_OPENAI_BASE_URL = "https://provider.example.test/v1/"
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    file_field = (
        premium_data_fixture.create_file_field(table=table) if with_file else None
    )
    field = FieldHandler().create_field(
        user,
        table,
        "ai",
        name="AI",
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-environment",
        ai_prompt="'Hello'",
        ai_file_field_id=file_field.id if file_field is not None else None,
    )
    values = {}
    if with_file:
        user_file = premium_data_fixture.create_user_file(
            uploaded_by=user, original_name="document.pdf"
        )
        premium_data_fixture.save_content_in_user_file(
            user_file, get_default_storage(), "%PDF-1.7 example"
        )
        values[file_field.db_column] = [{"name": user_file.name}]
    row = RowHandler().create_row(user, table, values)
    generator = AIValueGenerator(user, field)

    async def request(model, messages, model_settings, model_request_parameters):
        assert model.model_name == "gpt-environment"
        assert model.client.api_key == "environment-api-key"
        assert model.client.organization == organization
        assert str(model.client.base_url) == "https://provider.example.test/v1/"
        return ModelResponse(parts=[TextPart(content="environment-result")])

    def upload(files, **kwargs):
        assert files._client.api_key == "environment-api-key"
        assert files._client.organization == organization
        assert str(files._client.base_url) == "https://provider.example.test/v1/"
        assert kwargs["file"] == (user_file.name, b"%PDF-1.7 example")
        return SimpleNamespace(id="uploaded-document")

    deleted_files = []

    def delete(files, file_id):
        deleted_files.append(
            (
                files._client.api_key,
                files._client.organization,
                str(files._client.base_url),
                file_id,
            )
        )

    def generate_in_worker():
        queries = []

        def reject_query(execute, sql, params, many, context):
            queries.append(sql)
            raise AssertionError("AI field workers must not query the database")

        try:
            assert connection.connection is None
            with connection.execute_wrapper(reject_query):
                generator.generate_value_for(row)
            return queries, connection.connection is not None
        finally:
            # A regressing worker may open a connection before its query is rejected.
            connection.close()

    with (
        patch.object(
            OpenAIResponsesModel, "request", autospec=True, side_effect=request
        ) as request_mock,
        patch.object(Files, "create", autospec=True, side_effect=upload) as upload_mock,
        patch.object(Files, "delete", autospec=True, side_effect=delete) as delete_mock,
        ThreadPoolExecutor(max_workers=1) as executor,
    ):
        queries, opened_connection = executor.submit(generate_in_worker).result()

    assert queries == []
    assert opened_connection is False
    assert generator.results_queue.get_nowait().result == "environment-result"
    request_mock.assert_called_once()
    assert upload_mock.call_count == int(with_file)
    assert delete_mock.call_count == int(with_file)
    assert deleted_files == (
        [
            (
                "environment-api-key",
                organization,
                "https://provider.example.test/v1/",
                "uploaded-document",
            )
        ]
        if with_file
        else []
    )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_becomes_unavailable_when_its_instance_model_is_disabled(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    _, model = create_instance_openai_provider()
    field = FieldHandler().create_field(
        user,
        table,
        "ai",
        name="AI",
        ai_generative_ai_type="openai",
        ai_generative_ai_model=model.model_identifier,
        ai_prompt="'Hello'",
    )

    AIProviderHandler.update_model(model, is_enabled=False)

    with pytest.raises(ModelDoesNotBelongToType):
        AIFieldHandler.get_valid_model_type_or_raise(field)

    assert field.ai_generative_ai_type == "openai"
    assert field.ai_generative_ai_model == model.model_identifier


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_rejects_models_not_available_from_the_effective_provider(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    create_instance_openai_provider()

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "AI",
            "type": "ai",
            "ai_generative_ai_type": "openai",
            "ai_generative_ai_model": "gpt-not-configured",
            "ai_prompt": "'Hello'",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE"
