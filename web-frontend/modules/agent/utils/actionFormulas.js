import parseBaserowFormula from '@baserow/modules/core/formula/parser/parser'
import BaserowFormulaVisitor from '@baserow/modules/core/formula/parser/generated/BaserowFormulaVisitor'
import BaserowFormulaExecutionVisitor from '@baserow/modules/core/formula/parser/formulaExecutionVisitor'

class RemovedInputVisitor extends BaserowFormulaVisitor {
  constructor(ids) {
    super()
    this.paths = new Set(ids.map((id) => `tool_input.${id}`))
    this.ranges = []
    // Only literals/wrappers can resolve here: no function registry or context.
    this.literalVisitor = new BaserowFormulaExecutionVisitor(null)
  }

  visitFunctionCall(ctx) {
    if (
      ctx.func_name().getText().toLowerCase() === 'get' &&
      ctx.expr().length === 1
    ) {
      let path
      try {
        path = ctx.expr()[0].accept(this.literalVisitor)
      } catch {
        // Computed paths are invalid for action inputs; don't guess their value.
      }
      if (this.paths.has(path)) {
        this.ranges.push([ctx.start.start, ctx.stop.stop + 1])
        return
      }
    }
    return this.visitChildren(ctx)
  }
}

/** Remove only deleted input references, preserving text and other expressions. */
export function removeActionInputReferences(value, removedIds) {
  if (!removedIds.length || value === null || typeof value !== 'object')
    return value
  if (Array.isArray(value))
    return value.map((item) => removeActionInputReferences(item, removedIds))
  if (typeof value.formula === 'string' && value.mode) {
    if (!value.formula || value.mode === 'raw') return value
    const visitor = new RemovedInputVisitor(removedIds)
    try {
      visitor.visit(parseBaserowFormula(value.formula))
    } catch {
      // Preserve an unfinished/invalid formula rather than destroy user content.
      return value
    }
    let formula = value.formula
    for (const [start, end] of visitor.ranges.sort((a, b) => b[0] - a[0]))
      formula = `${formula.slice(0, start)}''${formula.slice(end)}`
    if (visitor.ranges.length && formula.trim() === "''") formula = ''
    return { ...value, formula }
  }
  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [
      key,
      removeActionInputReferences(item, removedIds),
    ])
  )
}
