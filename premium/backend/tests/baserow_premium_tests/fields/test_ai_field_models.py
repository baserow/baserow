import pytest


@pytest.mark.django_db
@pytest.mark.field_ai
def test_dynamic_get_attr(premium_data_fixture):
    field = premium_data_fixture.create_ai_field(ai_output_type="text")
    assert field.long_text_enable_rich_text is False

    with pytest.raises(AttributeError):
        field.non_existing_property
