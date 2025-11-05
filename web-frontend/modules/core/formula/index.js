import parseBaserowFormula from '@baserow/modules/core/formula/parser/parser'
import JavascriptExecutor from '@baserow/modules/core/formula/parser/javascriptExecutor'

/**
 * Resolves a formula in the context of the given context.
 *
 * @param {object} formulaCtx the input formula.
 * @param {object} functions the functions that can be used in the formula.
 * @param {object} RuntimeFormulaContext the context given to the formula when we meet the
 *   `get('something')` expression
 * @returns the result of the formula in the given context.
 */
export const resolveFormula = (
  formulaCtx,
  functions,
  RuntimeFormulaContext
) => {
  if (!formulaCtx.formula) {
    return formulaCtx.formula
  }

  if (formulaCtx.mode === 'raw') {
    // We don't need to resolve the formula for raw mode.
    return formulaCtx.formula
  }

  try {
    const tree = parseBaserowFormula(formulaCtx.formula)
    return new JavascriptExecutor(functions, RuntimeFormulaContext).visit(tree)
  } catch (err) {
    console.debug(`FORMULA DEBUG: ${err}`)
    return null
  }
}

export const isFormulaValid = (formula, functions) => {
  if (!formula) {
    return true
  }

  try {
    const tree = parseBaserowFormula(formula)
    new JavascriptExecutor(functions).visit(tree)
    return true
  } catch (err) {
    return false
  }
}
