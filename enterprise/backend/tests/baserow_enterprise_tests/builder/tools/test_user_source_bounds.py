import pytest
from pydantic import ValidationError

from baserow_enterprise.builder.tools.types.user_source import UserSourceSetup

LONG = "a" * 256


@pytest.mark.parametrize("name", [LONG, " "])
def test_too_long_or_blank_user_source_names_are_refused(name):
    with pytest.raises(ValidationError):
        UserSourceSetup(name=name, database_id=1)


def test_a_user_source_name_within_the_bounds_is_kept():
    assert UserSourceSetup(name=" Users ", database_id=1).name == "Users"
