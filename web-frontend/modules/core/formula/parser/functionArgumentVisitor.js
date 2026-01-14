import BaserowFormulaVisitor from '@baserow/modules/core/formula/parser/generated/BaserowFormulaVisitor'

/**
 * A visitor that validates formula function arguments during parsing.
 * Each function can define custom validation logic via validateArguments().
 *
 * This is used to validate formulas before execution, catching errors early
 * and providing better user feedback.
 */
export default class BaserowFormulaArgumentVisitor extends BaserowFormulaVisitor {
  /**
   * @param {FunctionCollection} functions - The collection of available formula functions
   * @param {Object} validationContext - Context needed for validation (e.g., dataProviderRegistry)
   */
  constructor(functions, validationContext = {}) {
    super()
    this.functions = functions
    this.validationContext = validationContext
  }

  /**
   * Visit a function call and validate its arguments.
   */
  visitFunctionCall(ctx) {
    const functionName = ctx.func_name().getText().toLowerCase()
    const functionArgumentExpressions = ctx.expr()
    const formulaFunctionType = this.functions.get(functionName)

    // Let each function validate its own arguments
    formulaFunctionType.validateArgs(
      functionArgumentExpressions,
      this.validationContext,
      ctx
    )

    // Continue visiting children to validate nested function calls
    for (const expr of functionArgumentExpressions) {
      expr.accept(this)
    }

    return null
  }
}
