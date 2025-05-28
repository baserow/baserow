from copy import deepcopy
from typing import Dict, List, Optional, Tuple, Type

from django.db.models import (
    BooleanField,
    DecimalField,
    Expression,
    FilteredRelation,
    JSONField,
    Model,
    Q,
    Value,
    fields,
)
from django.db.models.functions import Cast, JSONObject

from baserow.contrib.database.formula.ast.exceptions import UnknownFieldReference
from baserow.contrib.database.formula.ast.tree import (
    BaserowBooleanLiteral,
    BaserowDecimalLiteral,
    BaserowExpression,
    BaserowExpressionContext,
    BaserowFieldReference,
    BaserowFunctionCall,
    BaserowIntegerLiteral,
    BaserowStringLiteral,
)
from baserow.contrib.database.formula.ast.visitors import BaserowFormulaASTVisitor
from baserow.contrib.database.formula.expression_generator.django_expressions import (
    JSONArray,
)
from baserow.contrib.database.formula.types.formula_type import (
    BaserowFormulaInvalidType,
    BaserowFormulaType,
)
from baserow.core.formula.exceptions import formula_exception_handler
from baserow.core.formula.parser.exceptions import MaximumFormulaSizeError


def baserow_expression_to_update_django_expression(
    baserow_expression: BaserowExpression[BaserowFormulaType],
    model: Type[Model],
):
    return _baserow_expression_to_django_expression(baserow_expression, model, None)


def baserow_expression_to_single_row_update_django_expression(
    baserow_expression: BaserowExpression[BaserowFormulaType],
    model_instance: Model,
):
    return _baserow_expression_to_django_expression(
        baserow_expression, type(model_instance), model_instance, insert=False
    )


def baserow_expression_to_insert_django_expression(
    baserow_expression: BaserowExpression[BaserowFormulaType],
    model_instance: Model,
):
    return _baserow_expression_to_django_expression(
        baserow_expression, type(model_instance), model_instance, insert=True
    )


def _baserow_expression_to_django_expression(
    baserow_expression: BaserowExpression[BaserowFormulaType],
    model: Type[Model],
    model_instance: Optional[Model],
    insert=False,
) -> Expression:
    """
    Takes a BaserowExpression and converts it to a Django Expression which calculates
    the result of the expression when run on the provided model_instance or for the
    entire table when a model_instance is not provided.

    More specifically, when a model_instance is provided all field() references will
    be replaced by the values of those fields on the model_instance. If a model_instance
    is not provided instead these field references will be replaced by F() column
    references. When doing an create operation you will need to provide a model_instance
    as you cannot reference a column for a row that does not yet exist. Instead the
    initial defaults will be found and substituted in.

    :param baserow_expression: The BaserowExpression to convert.
    :param model: The Django model that the expression is being generated for.
    :param model_instance: If provided the expression will calculate the result for
        this single instance. If not provided then the expression will use F() column
        references and will calculate the result for every row in the table.
    :param insert: Must be set to True if the resulting expression will be used in
        a SQL INSERT statement. Will ensure any aggregate / lookup expressions are
        replaced with None as they cannot be calculated in an INSERT.
    :return: A Django Expression which can be used in a create operation when a
        model_instance is provided or an update operation when one is not provided.
    """

    try:
        if isinstance(baserow_expression.expression_type, BaserowFormulaInvalidType):
            return Value(None)
        else:
            inserting_aggregate = (
                baserow_expression.aggregate and model_instance is not None and insert
            )
            if inserting_aggregate:
                # When inserting a row we can't possibly calculate the aggregate result
                # as there is no row id that can be used to connect it to other tables.
                # Instead we need to insert a placeholder empty value which will then
                # get replaced later on with the correct value by an UPDATE statement.
                return baserow_expression.expression_type.placeholder_empty_value()
            else:
                generator = BaserowExpressionToDjangoExpressionGenerator(
                    model, model_instance
                )
                return baserow_expression.accept(generator).expression
    except RecursionError:
        raise MaximumFormulaSizeError()
    except Exception as e:
        formula_exception_handler(e)
        return Value(None)


JoinIdsType = List[Tuple[str, str]]


class WrappedExpressionWithMetadata:
    def __init__(
        self,
        expression: Expression,
        pre_annotations: Optional[Dict[str, FilteredRelation]] = None,
        aggregate_filters: Optional[List[Expression]] = None,
        join_ids: Optional[JoinIdsType] = None,
    ):
        self.expression = expression
        self._pre_annotations: Dict[str, FilteredRelation] = pre_annotations or {}
        self.aggregate_filters: List[Expression] = aggregate_filters or []
        self.join_ids: JoinIdsType = join_ids or []

    @property
    def pre_annotations(self) -> Dict[str, FilteredRelation]:
        # For some reason (possibly a Django bug), pre_annotations will be modified when
        # passed into annotate() call but we need to pass the same into multiple
        # annotate() calls.
        return deepcopy(self._pre_annotations)

    @classmethod
    def from_args(cls, expr, child_args: List["WrappedExpressionWithMetadata"]):
        pre_annotations = {}
        aggregate_filters = []
        join_ids = []
        for child in child_args:
            pre_annotations.update(child.pre_annotations)
            aggregate_filters.extend(child.aggregate_filters)
            join_ids.extend(child.join_ids)

        return WrappedExpressionWithMetadata(
            expr, pre_annotations, aggregate_filters, join_ids
        )


class BaserowExpressionToDjangoExpressionGenerator(
    BaserowFormulaASTVisitor[BaserowFormulaType, WrappedExpressionWithMetadata]
):
    """
    Visits a BaserowExpression replacing it with the equivalent Django Expression.

    If a model_instance is provided then any field references will be replaced with
    direct Value() expressions of those fields on that model_instance. If one is not
    provided then instead a F() expression will be used to reference that field.
    """

    def __init__(
        self,
        model: Type[Model],
        model_instance: Optional[Model],
    ):
        self.model_instance = model_instance
        self.model = model
        self.context = BaserowExpressionContext(model, model_instance)

    def visit_field_reference(
        self, field_reference: BaserowFieldReference[BaserowFormulaType]
    ) -> WrappedExpressionWithMetadata:
        db_column = field_reference.referenced_field_name
        generating_update_expression = self.model_instance is None
        if field_reference.is_lookup():
            return self._setup_lookup_expression(field_reference)
        elif generating_update_expression:
            model_field = self.model._meta.get_field(db_column)

            field_type = model_field.model.get_field_object(
                model_field.name, include_trash=True
            )["type"]

            return WrappedExpressionWithMetadata(
                field_type.get_formula_reference_to_model_field(
                    model_field, db_column, already_in_subquery=False
                )
            )
        elif self.model_instance.id and not hasattr(self.model_instance, db_column):
            raise UnknownFieldReference(db_column)
        else:
            return WrappedExpressionWithMetadata(
                self._generate_insert_expression(db_column)
            )

    def _generate_insert_expression(self, db_column):
        from baserow.contrib.database.fields.fields import (
            MultipleSelectManyToManyField,
            SingleSelectForeignKey,
        )

        model_field = self.model._meta.get_field(db_column)

        if isinstance(model_field, MultipleSelectManyToManyField):
            m2m_values = getattr(self.model_instance, "_m2m_values", {})
            instance_attr_value = m2m_values.get(db_column, None)
            if instance_attr_value is None:
                instance_attr_value = (
                    getattr(self.model_instance, db_column).all()
                    if self.model_instance.id
                    else []
                )

            options = [
                JSONObject(
                    **{
                        "id": Value(option.id),
                        "value": Value(option.value),
                        "color": Value(option.color),
                    }
                )
                for option in instance_attr_value
            ]

            return Cast(JSONArray(options), output_field=JSONField())

        instance_attr_value = getattr(self.model_instance, db_column)
        value = Value(instance_attr_value, output_field=model_field)

        if isinstance(model_field, SingleSelectForeignKey):
            model_field = JSONField()
            if instance_attr_value is not None:
                value = JSONObject(
                    **{
                        "value": Value(instance_attr_value.value),
                        "id": Value(instance_attr_value.id),
                        "color": Value(instance_attr_value.color),
                    }
                )

        # We need to cast and be super explicit what type this raw value is so
        # postgres does not get angry and claim this is an unknown type.
        return Cast(
            value,
            output_field=model_field,
        )

    # noinspection PyProtectedMember
    def _setup_lookup_expression(
        self, field_reference: BaserowFieldReference
    ) -> WrappedExpressionWithMetadata:
        path_to_lookup_from_lookup_table = field_reference.target_field
        m2m_to_lookup_table = field_reference.referenced_field_name

        lookup_table_model = self._get_remote_model(m2m_to_lookup_table, self.model)
        lookup_of_link_field = "__" in path_to_lookup_from_lookup_table
        if lookup_of_link_field:
            (
                model_field,
                filtered_join_to_lookup_field,
                join_ids,
                pre_annotations,
            ) = self._setup_extra_joins_to_linked_lookup_table(
                lookup_table_model,
                m2m_to_lookup_table,
                path_to_lookup_from_lookup_table,
            )
        else:
            (
                filtered_join_to_lookup_table,
                join_ids,
                pre_annotations,
            ) = self._setup_annotations_and_joins(
                lookup_table_model, m2m_to_lookup_table
            )

            model_field = lookup_table_model._meta.get_field(
                path_to_lookup_from_lookup_table
            )
            filtered_join_to_lookup_field = (
                filtered_join_to_lookup_table + "__" + path_to_lookup_from_lookup_table
            )

        field_type = model_field.model.get_field_object(model_field.name)["type"]

        return WrappedExpressionWithMetadata(
            field_type.get_formula_reference_to_model_field(
                model_field, filtered_join_to_lookup_field, already_in_subquery=True
            ),
            pre_annotations=pre_annotations,
            join_ids=join_ids,
        )

    # noinspection PyProtectedMember
    def _setup_extra_joins_to_linked_lookup_table(
        self, lookup_table_model, m2m_to_lookup_table, path_to_lookup_from_lookup_table
    ) -> Tuple[fields.Field, str, JoinIdsType, Dict[str, FilteredRelation]]:
        # If someone has done a lookup of a link row field in the other table,
        # the actual values we want to lookup are in that linked tables primary
        # field. To get at those values we need to do two joins, the first
        # above into the lookup table. The second from the lookup table to the
        # linked table.
        split_ref = path_to_lookup_from_lookup_table.split("__")
        link_field_in_lookup_table = split_ref[0]

        path_to_link_table = m2m_to_lookup_table + "__" + link_field_in_lookup_table

        link_table_model = self._get_remote_model(
            link_field_in_lookup_table, lookup_table_model
        )

        join_ids = [(m2m_to_lookup_table, lookup_table_model._meta.db_table)]
        (
            filtered_join_to_link_table,
            extra_join_ids,
            pre_annotations,
        ) = self._setup_annotations_and_joins(
            link_table_model, path_to_link_table, middle_link=m2m_to_lookup_table
        )

        primary_field_in_related_table = split_ref[1]
        model_field = link_table_model._meta.get_field(primary_field_in_related_table)
        return (
            model_field,
            filtered_join_to_link_table + "__" + primary_field_in_related_table,
            join_ids + extra_join_ids,
            pre_annotations,
        )

    # noinspection PyProtectedMember,PyMethodMayBeStatic
    def _get_remote_model(self, m2m_field_name, model):
        looked_up_link_table_model = model._meta.get_field(
            m2m_field_name
        ).remote_field.model
        return looked_up_link_table_model

    # noinspection PyProtectedMember
    def _setup_annotations_and_joins(
        self, model, join_path: str, middle_link=None
    ) -> Tuple[str, JoinIdsType, Dict[str, FilteredRelation]]:
        join_ids = [(join_path, str(model._meta.db_table))]
        pre_annotations = {}

        # We must ensure the annotation name has no __ as otherwise django will think
        # we aren't referring to an annotation but instead try to perform the joins.
        unique_annotation_path_name = f"not_trashed_{join_path}".replace("__", "_")
        relation_filters = {
            f"{join_path}__trashed": False,
            f"{join_path}__isnull": False,
        }
        if middle_link is not None:
            # We are joining via a middle m2m relation, ensure we don't use any trashed
            # rows there also.
            relation_filters[middle_link + "__trashed"] = False

        pre_annotations[unique_annotation_path_name] = FilteredRelation(
            join_path,
            condition=Q(**relation_filters),
        )
        return unique_annotation_path_name, join_ids, pre_annotations

    def visit_function_call(
        self, function_call: BaserowFunctionCall[BaserowFormulaType]
    ) -> WrappedExpressionWithMetadata:
        args: List[WrappedExpressionWithMetadata] = [
            expr.accept(self) for expr in function_call.args
        ]
        return function_call.to_django_expression_given_args(args, self.context)

    def visit_string_literal(
        self, string_literal: BaserowStringLiteral[BaserowFormulaType]
    ) -> WrappedExpressionWithMetadata:
        # We need to cast and be super explicit this is a text field so postgres
        # does not get angry and claim this is an unknown type.
        return WrappedExpressionWithMetadata(
            Cast(
                Value(string_literal.literal, output_field=fields.TextField()),
                output_field=fields.TextField(),
            )
        )

    def visit_int_literal(
        self, int_literal: BaserowIntegerLiteral[BaserowFormulaType]
    ) -> WrappedExpressionWithMetadata:
        return WrappedExpressionWithMetadata(
            Value(
                int_literal.literal,
                output_field=DecimalField(max_digits=50, decimal_places=0),
            )
        )

    def visit_decimal_literal(
        self, decimal_literal: BaserowDecimalLiteral
    ) -> WrappedExpressionWithMetadata:
        return WrappedExpressionWithMetadata(
            Value(
                decimal_literal.literal,
                output_field=DecimalField(
                    max_digits=50, decimal_places=decimal_literal.num_decimal_places()
                ),
            )
        )

    def visit_boolean_literal(
        self, boolean_literal: BaserowBooleanLiteral
    ) -> WrappedExpressionWithMetadata:
        return WrappedExpressionWithMetadata(
            Value(boolean_literal.literal, output_field=BooleanField())
        )
