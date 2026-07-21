import { resolveFormula } from '@baserow/modules/core/formula'
import RuntimeFormulaContext from '@baserow/modules/core/runtimeFormulaContext'

/**
 * Resolves a button field's URL formula against a row, client-side. Returns
 * an empty string when the formula is empty or cannot be resolved.
 */
export function resolveButtonUrl($registry, field, row, fields) {
  const formulaObject = field.url_formula
  if (!formulaObject?.formula) {
    return ''
  }
  const formulaFunctions = {
    get: (name) => $registry.get('runtimeFormulaFunction', name),
  }
  const runtimeFormulaContext = new Proxy(
    new RuntimeFormulaContext($registry.getAll('databaseDataProvider'), {
      row,
      fields,
    }),
    {
      get(target, prop) {
        return target.get(prop)
      },
    }
  )
  const result = resolveFormula(
    formulaObject,
    formulaFunctions,
    runtimeFormulaContext
  )
  return result === null || result === undefined ? '' : `${result}`
}
