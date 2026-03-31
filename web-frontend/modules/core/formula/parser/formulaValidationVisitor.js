import BaserowFormulaVisitor from '@baserow/modules/core/formula/parser/generated/BaserowFormulaVisitor'
import { InvalidFormulaType, UnknownOperatorError } from '@baserow/modules/core/formula/parser/errors.js'

/**
 * Marker symbol representing a value that will be resolved at execution time.
 *
 * During validation, when we encounter nested function calls (e.g., `is_even(get('foo.bar'))`),
 * the inner function's return value isn't available yet. Instead of failing validation
 * because we can't type-check an unknown value, we return this marker to indicate
 * "this will be a valid value at runtime, skip type validation for now."
 */
export const DeferredValue = Symbol('DeferredValue')

/**
 * A visitor that validates formula functions and their arguments during parsing.
 * Each function can define custom validation logic via validateArguments().
 *
 * This is used to validate formulas before execution, catching errors early
 * and providing better user feedback.
 */
export default class BaserowFormulaValidationVisitor extends BaserowFormulaVisitor {
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

  visitFieldReference(ctx) {
    throw new InvalidFormulaType("Unsupported function 'field'.")
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

  visitBinaryOp(ctx) {
    let op
    if (ctx.PLUS()) {
      op = 'add'
    } else if (ctx.MINUS()) {
      op = 'minus'
    } else if (ctx.SLASH()) {
      op = 'divide'
    } else if (ctx.EQUAL()) {
      op = 'equal'
    } else if (ctx.BANG_EQUAL()) {
      op = 'not_equal'
    } else if (ctx.STAR()) {
      op = 'multiply'
    } else if (ctx.GT()) {
      op = 'greater_than'
    } else if (ctx.LT()) {
      op = 'less_than'
    } else if (ctx.GTE()) {
      op = 'greater_than_or_equal'
    } else if (ctx.LTE()) {
      op = 'less_than_or_equal'
    } else if (ctx.AMP_AMP()) {
      op = 'and'
    } else if (ctx.PIPE_PIPE()) {
      op = 'or'
    } else {
      throw new UnknownOperatorError(ctx.getText())
    }
    return this.visitFunctionCall(ctx, op)
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
   * Parse arguments for validation, skipping DeferredValue instances.
   *
   * During validation, nested function calls return DeferredValue markers
   * since their actual values aren't available yet. We pass these through
   * unchanged rather than attempting to parse/cast them.
   */
  _parseArgsForValidation(formulaFunctionType, acceptedArgs) {
    if (!formulaFunctionType.args) {
      return acceptedArgs
    }

    return acceptedArgs.map((arg, index) => {
      if (arg === DeferredValue) {
        // Preserve deferred values - they'll be resolved at execution time
        return arg
      } else if (index < formulaFunctionType.args.length) {
        return formulaFunctionType.args[index].parse(arg)
      } else {
        return arg
      }
    })
  }

  /**
   * Visit a function call and validate its arguments.
   */
  visitFunctionCall(ctx, operatorFn = null) {
    const functionName = operatorFn || ctx.func_name().getText().toLowerCase()
    const functionArgumentExpressions = ctx.expr()
    let formulaFunctionType = null
    try {
      formulaFunctionType = this.functions.get(functionName)
    } catch (e) {
      throw new InvalidFormulaType(`Unsupported function '${functionName}'.`)
    }

    // Accept the argument expressions, then before parsing them,
    // confirm that we have the valid number of arguments.
    const acceptedArgs = Array.from(functionArgumentExpressions, (expr) =>
      expr.accept(this)
    )
    formulaFunctionType.validateNumberOfArgs(acceptedArgs, true)

    // Parse args, skipping DeferredValue instances
    const argsParsed = this._parseArgsForValidation(
      formulaFunctionType,
      acceptedArgs
    )

    // Only run validateArgs if none of the arguments are DeferredValue.
    // DeferredValue represents nested function calls whose values aren't
    // available until execution time, so we can't type-check them.
    const hasDeferred = argsParsed.some((arg) => arg === DeferredValue)
    if (!hasDeferred) {
      formulaFunctionType.validateArgs(argsParsed, { ctx, validationContext: this.validationContext})
    }

    // Return DeferredValue to indicate this function's result
    // will only be available at execution time
    return DeferredValue
  }
}
