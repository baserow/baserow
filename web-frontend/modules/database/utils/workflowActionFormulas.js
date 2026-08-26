// The id segment of `get('previous_action.<id>.field_1')`. Anchored on the
// `get(` so that only a reference is matched, and not a string that happens to
// read the same, such as `concat('x', 'previous_action.tmp.id')` or a URL
// ending `/docs/previous_action.html`.
const PREVIOUS_ACTION_ID = /(get\(\s*)(['"])previous_action\.([^.'"\s)]+)/g

// Service keys the server owns. Their formulas describe the selected table
// rather than anything the user typed, so they are neither rewritten nor read
// as references.
const READ_ONLY_KEYS = new Set([
  'schema',
  'context_data',
  'context_data_schema',
])

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
  return formula.replace(PREVIOUS_ACTION_ID, (match, prefix, quote, id) =>
    Object.prototype.hasOwnProperty.call(idMap, id)
      ? `${prefix}${quote}previous_action.${idMap[id]}`
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
        READ_ONLY_KEYS.has(key) ? item : rewriteActionFormulaIds(item, idMap),
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
      for (const [, , , id] of value.formula.matchAll(PREVIOUS_ACTION_ID)) {
        found.add(id)
      }
    } else {
      Object.entries(value).forEach(([key, item]) => {
        if (!READ_ONLY_KEYS.has(key)) {
          referencedActionIds(item, found)
        }
      })
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
      for (const [, , , id] of value.formula.matchAll(PREVIOUS_ACTION_ID)) {
        if (!/^\d+$/.test(id)) {
          found.add(id)
        }
      }
    } else {
      Object.entries(value).forEach(([key, item]) => {
        if (!READ_ONLY_KEYS.has(key)) {
          unresolvedActionIds(item, found)
        }
      })
    }
  }
  return [...found]
}
