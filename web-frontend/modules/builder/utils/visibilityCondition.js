import _ from 'lodash'
import parseBaserowFormula from '@baserow/modules/core/formula/parser/parser'
import BaserowFormula from '@baserow/modules/core/formula/parser/generated/BaserowFormula'
import BaserowFormulaVisitor from '@baserow/modules/core/formula/parser/generated/BaserowFormulaVisitor'

/**
 * The visibility of a form element depends on the form elements referenced by
 * its own visibility condition, and by the visibility conditions of its
 * ancestors. If following these dependencies leads back to the element, the
 * element can never be shown, e.g. a field shown depending on its own value,
 * two fields each shown depending on the other one, or a container shown
 * depending on a field inside it.
 */

const FORM_DATA_PROVIDER_TYPE = 'form_data'
const EMPTY_REFERENCES = new Set()
const REFERENCES_CACHE_MAX_SIZE = 512
const referencesCache = new Map()

/**
 * Collects the IDs of the form elements referenced by the
 * `get('form_data.<id>')` calls of a formula.
 */
class FormDataReferenceCollector extends BaserowFormulaVisitor {
  constructor() {
    super()
    this.elementIds = new Set()
  }

  visitFunctionCall(ctx) {
    const args = ctx.expr()
    if (
      ctx.func_name().getText().toLowerCase() === 'get' &&
      args.length > 0 &&
      args[0] instanceof BaserowFormula.StringLiteralContext
    ) {
      const [dataProviderType, elementId] = _.toPath(
        this.processString(args[0])
      )
      if (
        dataProviderType === FORM_DATA_PROVIDER_TYPE &&
        /^\d+$/.test(elementId)
      ) {
        this.elementIds.add(parseInt(elementId, 10))
      }
    }
    return this.visitChildren(ctx)
  }

  processString(ctx) {
    const literalWithoutOuterQuotes = ctx.getText().slice(1, -1)
    if (ctx.SINGLEQ_STRING_LITERAL() !== null) {
      return literalWithoutOuterQuotes.replace(/\\(['\\])/g, '$1')
    }
    return literalWithoutOuterQuotes.replace(/\\(["\\])/g, '$1')
  }
}

/**
 * Returns the IDs of the form elements referenced by a formula. The result is
 * cached by formula, and formulas not using form data aren't parsed at all.
 *
 * @param {Object|String} formula The formula object, or formula string.
 * @returns {Set<Number>} The referenced form element IDs.
 */
export function getFormDataReferences(formula) {
  const formulaString = typeof formula === 'string' ? formula : formula?.formula
  if (
    !formulaString ||
    formula?.mode === 'raw' ||
    !formulaString.includes(FORM_DATA_PROVIDER_TYPE)
  ) {
    return EMPTY_REFERENCES
  }

  let references = referencesCache.get(formulaString)
  if (references === undefined) {
    try {
      const collector = new FormDataReferenceCollector()
      parseBaserowFormula(formulaString).accept(collector)
      references = collector.elementIds
    } catch {
      references = EMPTY_REFERENCES
    }
    if (referencesCache.size >= REFERENCES_CACHE_MAX_SIZE) {
      referencesCache.delete(referencesCache.keys().next().value)
    }
    referencesCache.set(formulaString, references)
  }
  return references
}

/**
 * Resolves the visibility dependencies of the elements of the pages an
 * element's visibility can depend on: the element's page, the shared page and
 * the page being viewed. Dependencies are computed lazily, so only the
 * elements actually reached are inspected.
 */
class VisibilityDependencies {
  constructor(store, applicationContext, element) {
    const { builder, page: currentPage } = applicationContext
    const pages = [
      builder && store.getters['page/getById'](builder, element.page_id),
      builder && store.getters['page/getSharedPage'](builder),
      currentPage,
    ]
    this.store = store
    this.pages = _.uniqBy(pages.filter(Boolean), 'id')
    this.dependencies = new Map()
  }

  getPageOfElement(elementId) {
    return this.pages.find((page) =>
      this.store.getters['element/getElementById'](page, elementId)
    )
  }

  /**
   * @param {Number} elementId The element to get the dependencies of.
   * @returns {Set<Number>} The IDs of the form elements the visibility of the
   *   element depends on.
   */
  of(elementId) {
    if (!this.dependencies.has(elementId)) {
      const dependencies = new Set()
      const page = this.getPageOfElement(elementId)
      let current = page
        ? this.store.getters['element/getElementById'](page, elementId)
        : null
      const seen = new Set()
      while (current && !seen.has(current.id)) {
        seen.add(current.id)
        getFormDataReferences(current.visibility_condition).forEach((id) =>
          dependencies.add(id)
        )
        current = this.store.getters['element/getParent'](page, current)
      }
      this.dependencies.set(elementId, dependencies)
    }
    return this.dependencies.get(elementId)
  }

  /**
   * @param {Number} sourceId The element to start from.
   * @param {Set<Number>} targetIds The elements to look for.
   * @returns {Boolean} Whether the visibility of the source element depends on
   *   one of the target elements, directly or through other form elements. An
   *   element is considered to depend on itself.
   */
  dependsOnAny(sourceId, targetIds) {
    const toVisit = [sourceId]
    const seen = new Set()
    while (toVisit.length > 0) {
      const currentId = toVisit.pop()
      if (targetIds.has(currentId)) {
        return true
      }
      if (!seen.has(currentId)) {
        seen.add(currentId)
        toVisit.push(...this.of(currentId))
      }
    }
    return false
  }
}

/**
 * The element and its descendants: the elements whose visibility depends on
 * the element's visibility condition.
 */
function getAffectedElementIds(store, applicationContext, element) {
  const { builder } = applicationContext
  const page = builder
    ? store.getters['page/getById'](builder, element.page_id)
    : null
  const descendants = page
    ? store.getters['element/getDescendants'](page, element)
    : []
  return new Set([element.id, ...descendants.map(({ id }) => id)])
}

/**
 * Returns which of the given form elements the visibility condition of an
 * element can't reference, as the visibility of the element, or of an element
 * inside it, would then depend on itself.
 *
 * @param {Object} store The Vuex store.
 * @param {Object} applicationContext The application context.
 * @param {Object} element The element whose visibility condition is edited.
 * @param {Array<Number>} formElementIds The candidate form element IDs.
 * @returns {Set<Number>} The IDs which can't be referenced.
 */
export function getVisibilityCycleElementIds(
  store,
  applicationContext,
  element,
  formElementIds
) {
  const affectedIds = getAffectedElementIds(store, applicationContext, element)
  const dependencies = new VisibilityDependencies(
    store,
    applicationContext,
    element
  )
  return new Set(
    formElementIds.filter((id) => dependencies.dependsOnAny(id, affectedIds))
  )
}

/**
 * @param {Object} store The Vuex store.
 * @param {Object} applicationContext The application context.
 * @param {Object} element The element to check.
 * @returns {Boolean} Whether the visibility condition of the element
 *   references a form element whose visibility depends on the element itself,
 *   so that the element, or an element inside it, can never be shown.
 */
export function hasInvalidVisibilityCondition(
  store,
  applicationContext,
  element
) {
  const references = getFormDataReferences(element.visibility_condition)
  if (references.size === 0) {
    return false
  }
  return (
    getVisibilityCycleElementIds(store, applicationContext, element, [
      ...references,
    ]).size > 0
  )
}
