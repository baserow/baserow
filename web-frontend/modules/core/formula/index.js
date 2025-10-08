import parseBaserowFormula from '@baserow/modules/core/formula/parser/parser'
import JavascriptExecutor from '@baserow/modules/core/formula/parser/javascriptExecutor'

/**
 * Resolves a formula in the context of the given context.
 *
 * @param {object} formula the input formula.
 * @param {object} RuntimeFormulaContext the context given to the formula when we meet the
 *   `get('something')` expression
 * @returns the result of the formula in the given context.
 */
export const resolveFormula = (formula, functions, RuntimeFormulaContext) => {
  console.log('resolveFormula received formula:', formula)
  if (!formula.formula) {
    return ''
  }
  const tree = parseBaserowFormula(formula.formula)
  return new JavascriptExecutor(functions, RuntimeFormulaContext).visit(tree)
}

// /**
//  * Return True if the formula can be parsed, false otherwise. It doesn't try to resolve
//  * it as the context is missing so it won't detect bad data path or things like that.
//  *
//  * @param {str} formula the formula string.
//  * @returns whether or not the formula can be parsed.
//  */
// export const isValidFormula = (formula) => {
//   if (!formula) {
//     return true
//   }
//   try {
//     parseBaserowFormula(formula)
//     return true
//   } catch (e) {
//     return false
//   }
// }
