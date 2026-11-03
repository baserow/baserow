from django.contrib.postgres.fields import ArrayField
from django.db.models import (
    ExpressionWrapper,
    Func,
    JSONField,
    OuterRef,
    Subquery,
    TextField,
    Value,
)
from django.db.models.functions import JSONObject


def get_select_option_extractor(db_column, model_field):
    return ExpressionWrapper(
        JSONObject(
            **{
                "value": f"{db_column}__value",
                "id": f"{db_column}__id",
                "color": f"{db_column}__color",
            }
        ),
        output_field=model_field,
    )


def get_collaborator_extractor(db_column, model_field):
    return ExpressionWrapper(
        JSONObject(
            **{
                "name": f"{db_column}__name",
                "type": f"{db_column}__type",
                "id": f"{db_column}__id",
            }
        ),
        output_field=model_field,
    )


def wrap_in_subquery(subquery_expression, db_column, model):
    filters = {f"{db_column}__isnull": False}

    return ExpressionWrapper(
        Subquery(
            model.objects.filter(id=OuterRef("id"), **filters).values(
                result=subquery_expression
            )
        ),
        output_field=JSONField(),
    )


class CollaboratorNames(Func):
    """Read canonical names, falling back to legacy stored formula JSON only."""

    template = (
        "ARRAY(SELECT COALESCE(collaborator.value->>'name', "
        "collaborator.value->>'first_name') "
        "FROM jsonb_path_query(%(expressions)s) WITH ORDINALITY "
        "AS collaborator(value, position) ORDER BY collaborator.position)"
    )

    def __init__(self, expression, path="$[*]"):
        super().__init__(expression, Value(path), output_field=ArrayField(TextField()))
