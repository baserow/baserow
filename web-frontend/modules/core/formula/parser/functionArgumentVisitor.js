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

  visitRoot(ctx) {
    return ctx.expr().accept(this)
  }

  visitStringLiteral(ctx) {
    return this.processString(ctx)
  }

  visitDecimalLiteral(ctx) {
    return parseFloat(ctx.getText())
  }

  visitBooleanLiteral(ctx) {
    return ctx.TRUE() !== null
  }

  visitBrackets(ctx) {
    return ctx.expr().accept(this)
  }

  visitIdentifier(ctx) {
    return ctx.getText()
  }

  visitIntegerLiteral(ctx) {
    return parseInt(ctx.getText())
  }

  visitLeftWhitespaceOrComments(ctx) {
    return ctx.expr().accept(this)
  }

  visitRightWhitespaceOrComments(ctx) {
    return ctx.expr().accept(this)
  }

  processString(ctx) {
    const literalWithoutOuterQuotes = ctx.getText().slice(1, -1)
    let literal
    if (ctx.SINGLEQ_STRING_LITERAL() !== null) {
      literal = literalWithoutOuterQuotes.replace(/\\'/g, "'")
    } else {
      literal = literalWithoutOuterQuotes.replace(/\\"/g, '"')
    }
    return literal
  }

  /**
   * Visit a function call and validate its arguments.
   */
  visitFunctionCall(ctx) {
    const functionName = ctx.func_name().getText().toLowerCase()
    const functionArgumentExpressions = ctx.expr()
    const formulaFunctionType = this.functions.get(functionName)

    // Accept the argument expressions, then before parsing them,
    // confirm that we have the valid number of arguments.
    const acceptedArgs = Array.from(functionArgumentExpressions, (expr) =>
      expr.accept(this)
    )
    formulaFunctionType.validateNumberOfArgs(acceptedArgs, true)

    // Now that we have checked we have the correct number of args,
    // we can safely validate their types and values.
    const argsParsed = formulaFunctionType.parseArgs(acceptedArgs)
    formulaFunctionType.validateArgs(argsParsed, this.validationContext, ctx)

    // Continue visiting children to validate nested function calls
    for (const expr of functionArgumentExpressions) {
      expr.accept(this)
    }

    return null
  }
}
