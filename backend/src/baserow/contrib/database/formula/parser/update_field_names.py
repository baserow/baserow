from typing import Dict, Optional

from baserow.core.formula.parser.exceptions import MaximumFormulaSizeError
from baserow.core.formula.parser.generated.BaserowFormula import BaserowFormula
from baserow.core.formula.parser.generated.BaserowFormulaVisitor import (
    BaserowFormulaVisitor,
)
from baserow.core.formula.parser.parser import (
    convert_string_literal_token_to_string,
    convert_string_to_string_literal_token,
    get_parse_tree_for_formula,
)


# noinspection DuplicatedCode
class UpdateFieldNameFormulaVisitor(BaserowFormulaVisitor):
    """
    Visits nodes of the BaserowFormula antlr parse tree returning the formula in string
    form, but with field(name) and field_by_id(id) references replaced according to the
    input dictionaries.
    """

    def __init__(
        self,
        field_names_to_update: Optional[Dict[str, str]] = None,
        field_ids_to_replace_with_name_refs: Optional[Dict[int, str]] = None,
        field_names_to_replace_with_id_refs: Optional[Dict[str, int]] = None,
        via_field: Optional[str] = None,
    ):
        if field_names_to_update is None:
            field_names_to_update = {}
        if field_ids_to_replace_with_name_refs is None:
            field_ids_to_replace_with_name_refs = {}
        if field_names_to_replace_with_id_refs is None:
            field_names_to_replace_with_id_refs = {}

        self.field_names_to_replace_with_id_refs = field_names_to_replace_with_id_refs
        self.field_names_to_update = field_names_to_update
        self.field_ids_to_replace_with_name_refs = field_ids_to_replace_with_name_refs
        self.via_field = via_field

    def visitRoot(self, ctx: BaserowFormula.RootContext):
        return ctx.expr().accept(self)

    def visitStringLiteral(self, ctx: BaserowFormula.StringLiteralContext):
        return ctx.getText()

    def visitDecimalLiteral(self, ctx: BaserowFormula.DecimalLiteralContext):
        return ctx.getText()

    def visitBooleanLiteral(self, ctx: BaserowFormula.BooleanLiteralContext):
        return ctx.getText()

    def visitBrackets(self, ctx: BaserowFormula.BracketsContext):
        inner_expr = ctx.expr().accept(self)
        return f"({inner_expr})"

    def visitFunctionCall(self, ctx: BaserowFormula.FunctionCallContext):
        function_name = ctx.func_name().getText()
        args = [expr.accept(self) for expr in (ctx.expr())]
        args_with_any_field_names_replaced = ",".join(args)
        return f"{function_name}({args_with_any_field_names_replaced})"

    def visitBinaryOp(self, ctx: BaserowFormula.BinaryOpContext):
        args = [expr.accept(self) for expr in (ctx.expr())]
        return args[0] + ctx.op.text + args[1]

    def visitFunc_name(self, ctx: BaserowFormula.Func_nameContext):
        return ctx.getText()

    def visitIdentifier(self, ctx: BaserowFormula.IdentifierContext):
        return ctx.getText()

    def visitIntegerLiteral(self, ctx: BaserowFormula.IntegerLiteralContext):
        return ctx.getText()

    def visitFieldReference(self, ctx: BaserowFormula.FieldReferenceContext):
        reference = ctx.field_reference()
        is_single_quote_ref = reference.SINGLEQ_STRING_LITERAL()
        field_name = convert_string_literal_token_to_string(
            reference.getText(), is_single_quote_ref
        )
        if self.via_field is not None:
            # Don't do any field reference renaming as this is a field being re-named
            # in another table
            return ctx.getText()
        elif field_name in self.field_names_to_update:
            escaped_new_name = self._rename_and_escape(field_name, is_single_quote_ref)
            field = ctx.FIELD().getText()
            return f"{field}({escaped_new_name})"
        elif field_name in self.field_names_to_replace_with_id_refs:
            return (
                f"field_by_id({self.field_names_to_replace_with_id_refs[field_name]})"
            )
        else:
            return ctx.getText()

    def visitLookupFieldReference(
        self, ctx: BaserowFormula.LookupFieldReferenceContext
    ):
        reference = ctx.field_reference(0)
        is_single_quote_ref = reference.SINGLEQ_STRING_LITERAL()
        field_name = convert_string_literal_token_to_string(
            reference.getText(), is_single_quote_ref
        )
        lookup = ctx.field_reference(1)
        if self.via_field is None:
            if field_name in self.field_names_to_update:
                escaped_new_name = self._rename_and_escape(
                    field_name, is_single_quote_ref
                )
                return self._rebuild_lookup(ctx, escaped_new_name, lookup.getText())
            else:
                return ctx.getText()
        else:
            is_single_quote_lookup = lookup.SINGLEQ_STRING_LITERAL()
            lookup_field_name = convert_string_literal_token_to_string(
                lookup.getText(), is_single_quote_lookup
            )
            if (
                self.via_field == field_name
                and lookup_field_name in self.field_names_to_update
            ):
                escaped_lookup = self._rename_and_escape(
                    lookup_field_name, is_single_quote_lookup
                )
                return self._rebuild_lookup(ctx, reference.getText(), escaped_lookup)
            else:
                return ctx.getText()

    def _rebuild_lookup(self, ctx, via, lookup):
        lookup_text = ctx.LOOKUP().getText()
        whitespace = ctx.WHITESPACE()
        optional_whitespace = whitespace.getText() if whitespace else ""
        return f"{lookup_text}({via},{optional_whitespace}{lookup})"

    def _rename_and_escape(self, current_name, is_single_quote):
        new_name = self.field_names_to_update[current_name]
        escaped_new_name = convert_string_to_string_literal_token(
            new_name, is_single_quote
        )
        return escaped_new_name

    def visitFieldByIdReference(self, ctx: BaserowFormula.FieldByIdReferenceContext):
        field_id = int(str(ctx.INTEGER_LITERAL()))
        if field_id not in self.field_ids_to_replace_with_name_refs:
            return f"field('unknown field {field_id}')"
        new_name = self.field_ids_to_replace_with_name_refs[field_id]
        escaped_new_name = convert_string_to_string_literal_token(new_name, True)
        return f"field({escaped_new_name})"

    def visitLeftWhitespaceOrComments(
        self, ctx: BaserowFormula.LeftWhitespaceOrCommentsContext
    ):
        updated_expr = ctx.expr().accept(self)
        return ctx.ws_or_comment().getText() + updated_expr

    def visitRightWhitespaceOrComments(
        self, ctx: BaserowFormula.RightWhitespaceOrCommentsContext
    ):
        updated_expr = ctx.expr().accept(self)
        return updated_expr + ctx.ws_or_comment().getText()


def update_field_names(
    formula: str,
    field_names_to_update: Optional[Dict[str, str]] = None,
    field_ids_to_replace_with_name_refs: Optional[Dict[int, str]] = None,
    field_names_to_replace_with_id_refs: Optional[Dict[str, int]] = None,
    via_field: Optional[str] = None,
) -> str:
    """
    :param formula: The raw formula string to update field names in.
    :param field_names_to_update: A dictionary where the keys are the old
        field names with the values being the new names to replace the old with.
    :param field_ids_to_replace_with_name_refs: To replace field_by_id references
        with specific field names then provide this dictionary of field id to name
        which will swap field_by_id(key) for a field(value). If a field id is not found
        in this dict it will be swapped for field('unknown field {id}').
    :param field_names_to_replace_with_id_refs: To replace field references
        with specific field ids then provide this dictionary of field name to id
        which will swap field(key) for a field_by_id(value). If a field name is not
        found in this dict it will be left alone.
    :return: An updated formula string where field and field_by_id references have
        been updated accordingly. Whitespace and comments will not have been modified.
    """

    try:
        tree = get_parse_tree_for_formula(formula)
        return UpdateFieldNameFormulaVisitor(
            field_names_to_update,
            field_ids_to_replace_with_name_refs,
            field_names_to_replace_with_id_refs,
            via_field,
        ).visit(tree)
    except RecursionError:
        raise MaximumFormulaSizeError()
