// The id segment of `get('previous_action.<id>.field_1')`, matched as a whole
// segment so a literal that happens to contain the same characters is safe.
const PREVIOUS_ACTION_ID = /previous_action\.([^.'"\s)]+)/g

/**
 * Points a formula's `previous_action` references at the ids the server just
 * handed out.
 *
 * @param {String} formula The formula expression.
 * @param {Object} idMap Client id to the created action's real id.
 * @returns {String} The formula, with every mapped reference rewritten.
 */
export function rewriteFormulaActionIds(formula, idMap) {
  if (typeof formula !== 'string' || !formula.includes('previous_action.')) {
    return formula
  }
  return formula.replace(PREVIOUS_ACTION_ID, (match, id) =>
    Object.prototype.hasOwnProperty.call(idMap, id)
      ? `previous_action.${idMap[id]}`
      : match
  )
}

/**
 * The same, applied to every formula anywhere in an action's payload: a URL,
 * a row id, a field mapping's value.
 */
export function rewriteActionFormulaIds(value, idMap) {
  if (Array.isArray(value)) {
    return value.map((item) => rewriteActionFormulaIds(item, idMap))
  }
  if (value !== null && typeof value === 'object') {
    if (typeof value.formula === 'string') {
      return {
        ...value,
        formula: rewriteFormulaActionIds(value.formula, idMap),
      }
    }
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        rewriteActionFormulaIds(item, idMap),
      ])
    )
  }
  return value
}

/**
 * Every action a value's formulas reference, anywhere inside it.
 *
 * @param {*} value An action, or any part of one.
 * @returns {Array<String>} The referenced ids, as they appear in the formula.
 */
export function referencedActionIds(value, found = new Set()) {
  if (Array.isArray(value)) {
    value.forEach((item) => referencedActionIds(item, found))
  } else if (value !== null && typeof value === 'object') {
    if (typeof value.formula === 'string') {
      for (const [, id] of value.formula.matchAll(PREVIOUS_ACTION_ID)) {
        found.add(id)
      }
    } else {
      Object.values(value).forEach((item) => referencedActionIds(item, found))
    }
  }
  return [...found]
}

/**
 * The client ids a payload still carries after the rewrite.
 *
 * References only ever point backwards, so everything an action names is
 * already created by the time it is sent. Anything left is a broken invariant
 * rather than something to paper over, and must not reach the API.
 */
export function unresolvedActionIds(value, found = new Set()) {
  if (Array.isArray(value)) {
    value.forEach((item) => unresolvedActionIds(item, found))
  } else if (value !== null && typeof value === 'object') {
    if (typeof value.formula === 'string') {
      for (const [, id] of value.formula.matchAll(PREVIOUS_ACTION_ID)) {
        if (!/^\d+$/.test(id)) {
          found.add(id)
        }
      }
    } else {
      Object.values(value).forEach((item) => unresolvedActionIds(item, found))
    }
  }
  return [...found]
}
