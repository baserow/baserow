from baserow_premium.views.models import KanbanViewFieldOptions
from rest_framework import serializers

from baserow.contrib.database.api.rows.serializers import (
    get_example_multiple_rows_metadata_serializer,
    get_example_row_serializer_class,
)


class KanbanViewFieldOptionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = KanbanViewFieldOptions
        fields = ("hidden", "order")


class KanbanViewExampleResponseStackSerializer(serializers.Serializer):
    count = serializers.IntegerField(
        help_text="The total count of rows that are included in this group."
    )
    results = serializers.ListSerializer(
        help_text="All the rows that belong in this group related with the provided "
        "`limit` and `offset`.",
        child=get_example_row_serializer_class(example_type="get")(),
    )


def get_kanban_view_example_response_serializer():
    return type(
        "KanbanViewExampleResponseSerializer",
        (serializers.Serializer,),
        {
            "rows": serializers.DictField(
                child=KanbanViewExampleResponseStackSerializer(),
                help_text="Every select option related to the view's single select field can "
                "have its own entry like this.",
            ),
            "field_options": serializers.ListSerializer(
                child=KanbanViewFieldOptionsSerializer()
            ),
            "row_metadata": get_example_multiple_rows_metadata_serializer(),
        },
    )
