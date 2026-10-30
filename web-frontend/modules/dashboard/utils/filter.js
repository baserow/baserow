import parseBaserowFormula from '@baserow/modules/core/formula/parser/parser'
import BaserowFormula from '@baserow/modules/core/formula/parser/generated/BaserowFormula'
import BaserowFormulaVisitor from '@baserow/modules/core/formula/parser/generated/BaserowFormulaVisitor'
import BaserowFormulaExecutionVisitor from '@baserow/modules/core/formula/parser/formulaExecutionVisitor'

// Match the backend's core.utils.to_path, including trimmed segments and
// unquoted numeric selectors. Keep this opt-in so other formula consumers retain
// their existing path syntax.
const propertyPattern =
  /[^.[\]]+|\[(?:([^"'][^[]*)|(["'])((?:(?!\\2)[^\\\\]|\\\\.)*?)\\2)\]|(?=(?:\.|\[\])(?:\.|\[\]|$))/g

export function parseDashboardFormulaPath(path) {
  if (!path) return []
  const parts = path.startsWith('.') ? [''] : []
  for (const match of path.matchAll(propertyPattern)) {
    parts.push((match[1] || match[0]).trim())
  }
  return parts
}

export function isDashboardFilterPath(path) {
  return (
    path.length >= 1 &&
    path.length <= 2 &&
    /^[1-9][0-9]*$/.test(path[0]) &&
    (path.length === 1 || path[1] === '*' || /^[0-9]+$/.test(path[1]))
  )
}

export function getDashboardFilterValues(filter, values) {
  if (filter.mode !== 'dropdown' || !filter.multiple) {
    values = values.slice(0, 1)
  }
  return filter.mode === 'input' ? values.map((value) => value.trim()) : values
}

export const filterHasValue = (filter) =>
  !['empty', 'not_empty', 'is_even_and_whole'].includes(filter.operator)

export const filterHasDateValue = (filter) =>
  filter.type === 'date' && filter.operator?.startsWith('date_is')

const filterValueFormat = (filter) =>
  filterHasDateValue(filter)
    ? 'date'
    : filter.operator === 'date_equals_day_of_month'
      ? 'day_of_month'
      : 'plain'

export const filterHasOptions = (filter) =>
  filter.mode === 'dropdown' && filterHasValue(filter)

export function shouldResetFilterValues(previous, next) {
  return (
    previous != null &&
    ((previous.type || 'text') !== (next.type || 'text') ||
      previous.mode !== next.mode ||
      filterHasValue(previous) !== filterHasValue(next) ||
      filterValueFormat(previous) !== filterValueFormat(next) ||
      (previous.operator !== next.operator &&
        [previous.operator, next.operator].includes('date_is_within')) ||
      (next.mode === 'dropdown' && previous.multiple !== next.multiple))
  )
}

function unwrapExpression(expression) {
  const wrappers = [
    BaserowFormula.BracketsContext,
    BaserowFormula.LeftWhitespaceOrCommentsContext,
    BaserowFormula.RightWhitespaceOrCommentsContext,
  ]
  while (wrappers.some((type) => expression instanceof type)) {
    expression = expression.expr()
  }
  return expression
}

function getDashboardFilterPath(expression) {
  expression = unwrapExpression(expression)
  if (
    !(expression instanceof BaserowFormula.FunctionCallContext) ||
    expression.func_name().getText().toLowerCase() !== 'get' ||
    expression.expr().length !== 1
  )
    return null
  const argument = unwrapExpression(expression.expr(0))
  if (!(argument instanceof BaserowFormula.StringLiteralContext)) return null
  const literal = new BaserowFormulaExecutionVisitor().processString(argument)
  const [provider, ...path] = parseDashboardFormulaPath(literal)
  return provider === 'dashboard_filter' && isDashboardFilterPath(path)
    ? { filterId: Number(path[0]), index: path[1] }
    : null
}

export function getReferencedDashboardFilterId(formula) {
  if (!formula?.formula || formula.mode === 'raw') return null
  try {
    return (
      getDashboardFilterPath(parseBaserowFormula(formula.formula).expr())
        ?.filterId ?? null
    )
  } catch {
    // Incomplete expressions are still editable in the formula input.
    return null
  }
}

class DashboardFilterReferenceVisitor extends BaserowFormulaVisitor {
  constructor() {
    super()
    this.references = []
    this.dynamic = false
  }

  visitFunctionCall(ctx) {
    if (
      ctx.func_name().getText().toLowerCase() === 'get' &&
      (ctx.expr().length !== 1 ||
        !(
          unwrapExpression(ctx.expr(0)) instanceof
          BaserowFormula.StringLiteralContext
        ))
    )
      this.dynamic = true
    const reference = getDashboardFilterPath(ctx)
    if (reference) this.references.push(reference)
    return this.visitChildren(ctx)
  }
}

/** Combine service-owned dispatch inputs with referenced dashboard values. */
export function getDataSourceFilterInputs(source, filters, serviceType) {
  const { configuration, formulas } = serviceType?.getDispatchInputs(
    source
  ) ?? {
    configuration: source,
    formulas: null,
  }
  const references = new Set()
  let dynamic = formulas === null
  for (const formula of formulas ?? []) {
    if (!formula?.formula || formula.mode === 'raw') continue
    try {
      const visitor = new DashboardFilterReferenceVisitor()
      visitor.visit(parseBaserowFormula(formula.formula))
      visitor.references.forEach(({ filterId }) => references.add(filterId))
      dynamic ||= visitor.dynamic
    } catch {
      // Computed paths and incomplete formulas cannot be narrowed safely.
      dynamic = true
    }
  }
  if (dynamic) filters.forEach(({ id }) => references.add(id))
  const filtersById = new Map(filters.map((filter) => [filter.id, filter]))
  return {
    configuration,
    filters: [...references]
      .sort((a, b) => a - b)
      .map((id) => {
        const filter = filtersById.get(id)
        if (!filter) return { id }
        const { type, operator, mode, multiple } = filter
        return {
          id,
          type,
          operator,
          mode,
          multiple,
          values: getDashboardFilterValues(filter, filter.values ?? []),
        }
      }),
  }
}

export function hasActiveDashboardFilter(formula, filters) {
  if (!formula?.formula || formula.mode === 'raw') return false
  try {
    const visitor = new DashboardFilterReferenceVisitor()
    visitor.visit(parseBaserowFormula(formula.formula))
    return visitor.references.some(({ filterId, index }) => {
      const filter = filters.find(({ id }) => id === filterId)
      if (!filter) return false
      let values = getDashboardFilterValues(filter, filter.values ?? [])
      if (index !== undefined && index !== '*') {
        values = values.slice(Number(index), Number(index) + 1)
      }
      return values.some((value) => value.trim() !== '')
    })
  } catch {
    return false
  }
}
