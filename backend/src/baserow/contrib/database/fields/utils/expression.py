from django.db.models import ExpressionWrapper, JSONField, OuterRef, Subquery
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
                "first_name": f"{db_column}__first_name",
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
