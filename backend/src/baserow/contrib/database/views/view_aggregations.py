from typing import Dict

from django.db.models import (
    Avg,
    Case,
    Count,
    Exists,
    Field,
    ManyToManyField,
    Max,
    Min,
    OuterRef,
    StdDev,
    Sum,
    Variance,
    When,
)

from baserow.contrib.database.db.aggregations import Percentile
from baserow.contrib.database.fields.field_types import (
    AutonumberFieldType,
    BooleanFieldType,
    CreatedByFieldType,
    CreatedOnFieldType,
    DateFieldType,
    DurationFieldType,
    EmailFieldType,
    FileFieldType,
    FormulaFieldType,
    LastModifiedByFieldType,
    LastModifiedFieldType,
    LinkRowFieldType,
    LongTextFieldType,
    MultipleSelectFieldType,
    NumberFieldType,
    PasswordFieldType,
    PhoneNumberFieldType,
    RatingFieldType,
    SingleSelectFieldType,
    TextFieldType,
    URLFieldType,
)
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.formula import (
    BaserowFormulaBooleanType,
    BaserowFormulaCharType,
    BaserowFormulaDateType,
    BaserowFormulaNumberType,
    BaserowFormulaTextType,
)
from baserow.contrib.database.formula.types.formula_types import (
    BaserowFormulaSingleFileType,
)

from .registries import ViewAggregationType
from .utils import AnnotatedAggregation, DistributionAggregation

# See official django documentation for list of aggregator:
# https://docs.djangoproject.com/en/4.0/ref/models/querysets/#aggregation-functions


def get_has_relations_annotation(field_name: str, model_field: Field) -> Dict:
    """
    Generates an annotation dict that can be applied to a queryset. This can be used
    to check whether a row has many to many relationships in a performant way.
    """

    through_model = model_field.remote_field.through
    reversed_field = through_model._meta.get_fields()[1].name
    subquery = through_model.objects.filter(**{f"{reversed_field}_id": OuterRef("pk")})
    return {f"has_relations_{field_name}": Exists(subquery)}


class CountViewAggregationType(ViewAggregationType):
    """
    The count aggregation counts how many rows
    are in the table.
    """

    type = "count"
    allowed_in_view = False

    compatible_field_types = [
        TextFieldType.type,
        LongTextFieldType.type,
        URLFieldType.type,
        NumberFieldType.type,
        RatingFieldType.type,
        BooleanFieldType.type,
        DateFieldType.type,
        DurationFieldType.type,
        LastModifiedFieldType.type,
        LastModifiedByFieldType.type,
        CreatedOnFieldType.type,
        CreatedByFieldType.type,
        LinkRowFieldType.type,
        EmailFieldType.type,
        FileFieldType.type,
        PhoneNumberFieldType.type,
        SingleSelectFieldType.type,
        MultipleSelectFieldType.type,
        PasswordFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaTextType.type,
            BaserowFormulaCharType.type,
            BaserowFormulaNumberType.type,
            BaserowFormulaDateType.type,
            BaserowFormulaBooleanType.type,
            FormulaFieldType.array_of(BaserowFormulaSingleFileType.type),
        ),
    ]

    def get_aggregation(self, field_name, model_field, field):
        return Count(
            "id",
            distinct=True,
        )


class EmptyCountViewAggregationType(ViewAggregationType):
    """
    The empty count aggregation counts how many values are considered empty for
    the given field.
    """

    type = "empty_count"

    compatible_field_types = [
        TextFieldType.type,
        LongTextFieldType.type,
        URLFieldType.type,
        NumberFieldType.type,
        RatingFieldType.type,
        BooleanFieldType.type,
        DateFieldType.type,
        DurationFieldType.type,
        LastModifiedFieldType.type,
        LastModifiedByFieldType.type,
        CreatedOnFieldType.type,
        CreatedByFieldType.type,
        LinkRowFieldType.type,
        EmailFieldType.type,
        FileFieldType.type,
        PhoneNumberFieldType.type,
        SingleSelectFieldType.type,
        MultipleSelectFieldType.type,
        PasswordFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaTextType.type,
            BaserowFormulaCharType.type,
            BaserowFormulaNumberType.type,
            BaserowFormulaDateType.type,
            BaserowFormulaBooleanType.type,
            FormulaFieldType.array_of(BaserowFormulaSingleFileType.type),
        ),
    ]

    def get_aggregation(self, field_name, model_field, field):
        field_type = field_type_registry.get_by_model(field)

        if isinstance(model_field, ManyToManyField):
            # Using the normal `Count` aggregation for multiple manytomany fields
            # results makes the response time exponentially slower for each field.
            # This alternative way keeps it performant.
            return AnnotatedAggregation(
                annotations=get_has_relations_annotation(field_name, model_field),
                aggregation=Count(
                    Case(When(then=1, **{f"has_relations_{field_name}": False}))
                ),
            )
        else:
            return Count(
                "id",
                distinct=True,
                filter=field_type.empty_query(field_name, model_field, field),
            )


class NotEmptyCountViewAggregationType(EmptyCountViewAggregationType):
    """
    The empty count aggregation counts how many values aren't considered empty for
    the given field.
    """

    type = "not_empty_count"

    def get_aggregation(self, field_name, model_field, field):
        field_type = field_type_registry.get_by_model(field)

        if isinstance(model_field, ManyToManyField):
            # Using the normal `Count` aggregation for multiple manytomany fields
            # results makes the response time exponentially slower for each field.
            # This alternative way keeps it performant.
            return AnnotatedAggregation(
                annotations=get_has_relations_annotation(field_name, model_field),
                aggregation=Count(
                    Case(When(then=1, **{f"has_relations_{field_name}": True}))
                ),
            )
        else:
            return Count(
                "id",
                distinct=True,
                filter=~field_type.empty_query(field_name, model_field, field),
            )


class UniqueCountViewAggregationType(ViewAggregationType):
    """
    The aggregation compute the count of distinct value for the given field.
    """

    type = "unique_count"

    compatible_field_types = [
        TextFieldType.type,
        LongTextFieldType.type,
        URLFieldType.type,
        NumberFieldType.type,
        RatingFieldType.type,
        DateFieldType.type,
        LastModifiedFieldType.type,
        LastModifiedByFieldType.type,
        CreatedOnFieldType.type,
        CreatedByFieldType.type,
        EmailFieldType.type,
        PhoneNumberFieldType.type,
        SingleSelectFieldType.type,
        DurationFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaTextType.type,
            BaserowFormulaCharType.type,
            BaserowFormulaNumberType.type,
            BaserowFormulaDateType.type,
        ),
    ]

    def get_aggregation(self, field_name, model_field, field):
        return Count(
            field_name,
            distinct=True,
        )


class MinViewAggregationType(ViewAggregationType):
    """
    Compute the minimum value for the given field.
    """

    type = "min"

    compatible_field_types = [
        DateFieldType.type,
        NumberFieldType.type,
        RatingFieldType.type,
        DateFieldType.type,
        LastModifiedFieldType.type,
        CreatedOnFieldType.type,
        AutonumberFieldType.type,
        DurationFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaNumberType.type,
            BaserowFormulaDateType.type,
        ),
    ]

    def get_aggregation(self, field_name, model_field, field):
        return Min(field_name)


class MaxViewAggregationType(ViewAggregationType):
    """
    Compute the maximum value for the given field.
    """

    type = "max"

    compatible_field_types = [
        DateFieldType.type,
        NumberFieldType.type,
        RatingFieldType.type,
        DateFieldType.type,
        LastModifiedFieldType.type,
        CreatedOnFieldType.type,
        AutonumberFieldType.type,
        DurationFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaNumberType.type,
            BaserowFormulaDateType.type,
        ),
    ]

    def get_aggregation(self, field_name, model_field, field):
        return Max(field_name)


class SumViewAggregationType(ViewAggregationType):
    """
    Compute the sum of all the values of the given field.
    """

    type = "sum"

    compatible_field_types = [
        NumberFieldType.type,
        RatingFieldType.type,
        DurationFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaNumberType.type,
        ),
    ]

    def get_aggregation(self, field_name, model_field, field):
        return Sum(field_name)


class AverageViewAggregationType(ViewAggregationType):
    """
    Compute the average of all the values of the given field.
    """

    type = "average"

    compatible_field_types = [
        NumberFieldType.type,
        RatingFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaNumberType.type,
        ),
    ]

    def get_aggregation(self, field_name, model_field, field):
        field_type = field_type_registry.get_by_model(field)

        return Avg(
            field_name,
            filter=~field_type.empty_query(field_name, model_field, field),
        )


class StdDevViewAggregationType(ViewAggregationType):
    """
    Compute the standard deviation of the values of the given field.
    """

    type = "std_dev"

    compatible_field_types = [
        NumberFieldType.type,
        RatingFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaNumberType.type,
        ),
    ]

    def get_aggregation(self, field_name, model_field, field):
        return StdDev(field_name)


class VarianceViewAggregationType(ViewAggregationType):
    """
    Compute the variance of the values of the given field.
    """

    type = "variance"

    compatible_field_types = [
        NumberFieldType.type,
        RatingFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaNumberType.type,
        ),
    ]

    def get_aggregation(self, field_name, model_field, field):
        return Variance(field_name)


class MedianViewAggregationType(ViewAggregationType):
    """
    Compute the median of the values of the given field.
    """

    type = "median"

    compatible_field_types = [
        NumberFieldType.type,
        RatingFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaNumberType.type,
        ),
    ]

    def get_aggregation(self, field_name, model_field, field):
        return Percentile(field_name, 0.5)


class DecileViewAggregationType(ViewAggregationType):
    """
    Compute deciles of the values of the given field.
    """

    type = "decile"

    compatible_field_types = [
        NumberFieldType.type,
        RatingFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaNumberType.type,
        ),
    ]

    def get_aggregation(self, field_name, model_field, field):
        return Percentile(field_name, [x / 10 for x in range(1, 10)])


class RangeViewAggregationType(ViewAggregationType):
    """
    Compute the min and max of the values of the given field.
    """

    type = "range"

    compatible_field_types = [
        DateFieldType.type,
        NumberFieldType.type,
        RatingFieldType.type,
        DateFieldType.type,
        LastModifiedFieldType.type,
        CreatedOnFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaNumberType.type,
            BaserowFormulaDateType.type,
        ),
    ]

    def get_aggregation(self, field_name, model_field, field):
        return {"min": Min(field_name), "max": Max(field_name)}


class DistributionViewAggregationType(ViewAggregationType):
    """
    Compute the distribution of values
    """

    type = "distribution"

    compatible_field_types = [
        TextFieldType.type,
        LongTextFieldType.type,
        URLFieldType.type,
        NumberFieldType.type,
        RatingFieldType.type,
        DateFieldType.type,
        LastModifiedFieldType.type,
        LastModifiedByFieldType.type,
        CreatedOnFieldType.type,
        CreatedByFieldType.type,
        EmailFieldType.type,
        PhoneNumberFieldType.type,
        SingleSelectFieldType.type,
        DurationFieldType.type,
        BooleanFieldType.type,
        FormulaFieldType.compatible_with_formula_types(
            BaserowFormulaBooleanType.type,
            BaserowFormulaCharType.type,
            BaserowFormulaDateType.type,
            BaserowFormulaNumberType.type,
            BaserowFormulaTextType.type,
        ),
    ]

    def get_aggregation(self, field_name, model_field, field):
        field_type = field_type_registry.get_by_model(field)
        return DistributionAggregation(
            field_type.get_distribution_group_by_value(field_name)
        )
