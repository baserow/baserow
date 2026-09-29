from django.core.exceptions import FieldDoesNotExist

import pytest

from baserow.contrib.database.fields.models import SingleSelectField
from baserow_premium.fields.models import AIField


@pytest.mark.django_db
@pytest.mark.field_ai
def test_dynamic_get_attr(premium_data_fixture):
    field = premium_data_fixture.create_ai_field(ai_output_type="choice")
    with pytest.raises(FieldDoesNotExist):
        AIField._meta.get_field("single_select_default")

    assert (
        field.single_select_default
        is SingleSelectField._meta.get_field("single_select_default").default
    )

    with pytest.raises(AttributeError):
        field.non_existing_property
