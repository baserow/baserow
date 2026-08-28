import parseBaserowFormula from '@baserow/modules/core/formula/parser/parser'
import BaserowFormula from '@baserow/modules/core/formula/parser/generated/BaserowFormula'
import BaserowFormulaVisitor from '@baserow/modules/core/formula/parser/generated/BaserowFormulaVisitor'

// The data provider a reference names, and the segment that follows it.
const PREVIOUS_ACTION = 'previous_action.'

// Only reached when the formula cannot be parsed. It reads a reference the
// grammar would not, a quoted literal for instance, which is the safe way
// round: a client id missed here is one that reaches the API.
const PREVIOUS_ACTION_ID = /previous_action\.([^.'"\s)]+)/g

// Service keys the server owns. Their formulas describe the selected table
// rather than anything the user typed, so they are neither rewritten nor read
// as references.
const READ_ONLY_KEYS = new Set([
  'schema',
  'context_data',
  'context_data_schema',
])

/**
 * Collects the `previous_action` references a formula makes, as the character
 * range each id occupies. Walking the tree is what tells a reference apart
 * from a string that merely reads like one, and it sees `GET(` too, since the
 * visitors that run a formula lower the function name.
 */
const isWhitespaceWrapper = (ctx) =>
  ctx instanceof BaserowFormula.LeftWhitespaceOrCommentsContext ||
  ctx instanceof BaserowFormula.RightWhitespaceOrCommentsContext

/**
 * The expression itself, with the nodes the grammar wraps it in for the spaces
 * and comments around it peeled off. `get( 'x' )` is the same reference as
 * `get('x')`.
 */
function unwrap(ctx) {
  let inner = ctx
  while (isWhitespaceWrapper(inner)) {
    inner = inner.expr()
  }
  return inner
}

class PreviousActionReferenceVisitor extends BaserowFormulaVisitor {
  constructor() {
    super()
    this.references = []
  }

  visitFunctionCall(ctx) {
    // Error recovery can leave a call without a name or arguments.
    const name = ctx.func_name()?.getText()?.toLowerCase()
    const [first] = ctx.expr() || []
    const argument = first && unwrap(first)
    if (
      name === 'get' &&
      argument instanceof BaserowFormula.StringLiteralContext
    ) {
      this.collect(argument)
    }
    return this.visitChildren(ctx)
  }

  collect(ctx) {
    const path = ctx.getText().slice(1, -1)
    if (!path.startsWith(PREVIOUS_ACTION)) {
      return
    }
    const [id] = path.slice(PREVIOUS_ACTION.length).split('.')
    if (!id) {
      return
    }
    // `+ 1` for the opening quote. Nothing before the id can be escaped, so
    // the text offsets and the source offsets agree up to this point.
    const start = ctx.start.start + 1 + PREVIOUS_ACTION.length
    this.references.push({ id, start, end: start + id.length })
  }
}

/**
 * @param {String} formula The formula expression.
 * @returns {Array<Object>|null} Each reference and where its id sits, in the
 *   order they appear, or null when the formula could not be read at all.
 */
function referencesIn(formula) {
  try {
    const visitor = new PreviousActionReferenceVisitor()
    // Parsed leniently: the editor asks what a half typed formula references.
    visitor.visit(parseBaserowFormula(formula, false))
    return visitor.references.sort((a, b) => a.start - b.start)
  } catch (error) {
    return null
  }
}

/** The ids a formula references, however the formula reads. */
function idsIn(formula) {
  // A reference spells this out, so anything without it is not worth parsing.
  // The editor asks for these on every keystroke.
  if (!formula.includes(PREVIOUS_ACTION)) {
    return []
  }
  const references = referencesIn(formula)
  if (references === null) {
    return [...formula.matchAll(PREVIOUS_ACTION_ID)].map(([, id]) => id)
  }
  return references.map(({ id }) => id)
}

/**
 * Points a formula's `previous_action` references at the ids the server just
 * handed out.
 *
 * @param {String} formula The formula expression.
 * @param {Object} idMap Client id to the created action's real id.
 * @returns {String} The formula, with every mapped reference rewritten.
 */
export function rewriteFormulaActionIds(formula, idMap) {
  if (typeof formula !== 'string' || !formula.includes(PREVIOUS_ACTION)) {
    return formula
  }
  const references = referencesIn(formula)
  if (references === null) {
    // Rewriting by hand could corrupt a formula that is already broken, and
    // `unresolvedActionIds` refuses the save either way.
    return formula
  }
  // Back to front, so an earlier replacement cannot move a later range.
  return references.reduceRight(
    (rewritten, { id, start, end }) =>
      Object.prototype.hasOwnProperty.call(idMap, id)
        ? `${rewritten.slice(0, start)}${idMap[id]}${rewritten.slice(end)}`
        : rewritten,
    formula
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
 * Walks a value's formulas, handing each id it references to `collect`.
 */
function eachReferencedId(value, collect) {
  if (Array.isArray(value)) {
    value.forEach((item) => eachReferencedId(item, collect))
  } else if (value !== null && typeof value === 'object') {
    if (typeof value.formula === 'string') {
      idsIn(value.formula).forEach(collect)
    } else {
      Object.entries(value).forEach(([key, item]) => {
        if (!READ_ONLY_KEYS.has(key)) {
          eachReferencedId(item, collect)
        }
      })
    }
  }
}

/**
 * Every action a value's formulas reference, anywhere inside it.
 *
 * @param {*} value An action, or any part of one.
 * @param {Set} found Collected into, so a caller walking an action key by key
 *   can gather the whole of it.
 * @returns {Array<String>} The referenced ids, as they appear in the formula.
 */
export function referencedActionIds(value, found = new Set()) {
  eachReferencedId(value, (id) => found.add(id))
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
  eachReferencedId(value, (id) => {
    if (!/^\d+$/.test(id)) {
      found.add(id)
    }
  })
  return [...found]
}
