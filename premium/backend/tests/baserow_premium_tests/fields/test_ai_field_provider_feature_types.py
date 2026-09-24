import pytest

from baserow.core.ai_provider.constants import AI_PROVIDER_FEATURE_AI_FIELDS
from baserow.core.ai_provider.registries import (
    ai_provider_model_feature_type_registry,
)


def get_feature_type():
    return ai_provider_model_feature_type_registry.get(AI_PROVIDER_FEATURE_AI_FIELDS)


@pytest.mark.django_db
def test_ai_fields_count_model_references(premium_data_fixture):
    table = premium_data_fixture.create_database_table()
    workspace = table.database.workspace
    other_table = premium_data_fixture.create_database_table()
    other_workspace = other_table.database.workspace
    premium_data_fixture.create_ai_field(
        table=table,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="field-model",
    )
    premium_data_fixture.create_ai_field(
        table=table,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="another-model",
    )
    premium_data_fixture.create_ai_field(
        table=table,
        ai_generative_ai_type="anthropic",
        ai_generative_ai_model="field-model",
    )
    trashed_field = premium_data_fixture.create_ai_field(
        table=table,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="field-model",
    )
    trashed_field.trashed = True
    trashed_field.save()
    premium_data_fixture.create_ai_field(
        table=other_table,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="field-model",
    )
    feature_type = get_feature_type()

    assert feature_type.count_model_references("openai", "field-model", workspace) == 1
    assert (
        feature_type.count_model_references("openai", "field-model", other_workspace)
        == 1
    )
    assert feature_type.count_model_references("openai", "field-model", None) == 2
    assert feature_type.count_model_references("openai", "unknown-model", None) == 0
    assert feature_type.count_model_references("mistral", "field-model", None) == 0


@pytest.mark.django_db
def test_ai_fields_count_model_references_ignores_trashed_ancestors(
    premium_data_fixture,
):
    table = premium_data_fixture.create_database_table()
    database = table.database
    workspace = database.workspace
    premium_data_fixture.create_ai_field(
        table=table,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="field-model",
    )
    feature_type = get_feature_type()
    assert feature_type.count_model_references("openai", "field-model", None) == 1

    table.trashed = True
    table.save()

    assert feature_type.count_model_references("openai", "field-model", None) == 0
    assert feature_type.count_model_references("openai", "field-model", workspace) == 0

    table.trashed = False
    table.save()
    database.trashed = True
    database.save()

    assert feature_type.count_model_references("openai", "field-model", None) == 0

    database.trashed = False
    database.save()
    workspace.trashed = True
    workspace.save()

    assert feature_type.count_model_references("openai", "field-model", None) == 0
