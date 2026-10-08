import { TestApp } from '@baserow/test/helpers/testApp'
import {
  getFormDataReferences,
  getVisibilityCycleElementIds,
  hasInvalidVisibilityCondition,
} from '@baserow/modules/builder/utils/visibilityCondition'

const condition = (formula) => ({ formula, mode: 'simple', version: '0.1' })
const formData = (id) => condition(`get('form_data.${id}')`)

describe('getFormDataReferences', () => {
  test.each([
    ['', []],
    ["'form_data'", []],
    ["get('form_data.12')", [12]],
    ['get("form_data.12")', [12]],
    ["get('form_data.12.*')", [12]],
    ["get('page_parameter.id')", []],
    ["get('data_source.3.field_12')", []],
    ["and(get('form_data.1'), not(get('form_data.2')))", [1, 2]],
    ["get('form_data.1') = get('data_source.form_data.2')", [1]],
    ["get('form_data.not_an_id')", []],
    ["get('form_data.1'", []],
  ])('%s references %j', (formula, expected) => {
    expect([...getFormDataReferences(condition(formula))]).toEqual(expected)
    expect([...getFormDataReferences(formula)]).toEqual(expected)
  })

  test('ignores raw formulas', () => {
    expect(
      getFormDataReferences({ formula: "get('form_data.1')", mode: 'raw' }).size
    ).toBe(0)
  })
})

describe('visibility condition cycles', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  /**
   * Page 1:
   *   form (1)
   *     column (2)
   *       input (3)
   *     input (4)
   *   input (5)
   * Shared page:
   *   header (10)
   *     input (11)
   */
  const setup = (conditions = {}) => {
    const builder = { id: 1 }
    const element = (id, type, pageId) => ({
      id,
      type,
      page_id: pageId,
      visibility_condition: conditions[id] || condition(''),
    })
    const page = { id: 1, shared: false }
    page.elementMap = {
      1: element(1, 'form_container', 1),
      2: element(2, 'column', 1),
      3: element(3, 'input_text', 1),
      4: element(4, 'input_text', 1),
      5: element(5, 'input_text', 1),
    }
    page.graph = {
      0: 1,
      1: { next: { '': [5] }, children: { '': [2] } },
      2: { next: { '': [4] }, children: { 0: [3] } },
      3: {},
      4: {},
      5: {},
    }
    const sharedPage = { id: 2, shared: true }
    sharedPage.elementMap = {
      10: element(10, 'header', 2),
      11: element(11, 'input_text', 2),
    }
    sharedPage.graph = { 0: 10, 10: { children: { '': [11] } }, 11: {} }

    const pages = [page, sharedPage]
    const { getters } = testApp.store
    const store = {
      getters: {
        'page/getById': (_builder, id) => pages.find((p) => p.id === id),
        'page/getSharedPage': () => sharedPage,
        'element/getElementById': getters['element/getElementById'],
        'element/getParent': getters['element/getParent'],
        'element/getDescendants': getters['element/getDescendants'],
      },
    }
    const applicationContext = { builder, page }
    const isInvalid = (id) =>
      hasInvalidVisibilityCondition(
        store,
        applicationContext,
        page.elementMap[id] || sharedPage.elementMap[id]
      )
    return { store, applicationContext, page, sharedPage, isInvalid }
  }

  test.each([
    ['a field referencing itself', { 3: formData(3) }, [3]],
    [
      'fields referencing each other',
      { 4: formData(5), 5: formData(4) },
      [4, 5],
    ],
    [
      'a longer chain',
      { 3: formData(4), 4: formData(5), 5: formData(3) },
      [3, 4, 5],
    ],
    ['a container referencing a child', { 2: formData(3) }, [2]],
    ['a container referencing a nested child', { 1: formData(3) }, [1]],
    [
      'a field referencing a field whose container references it',
      { 5: formData(3), 2: formData(5) },
      [2, 5],
    ],
    [
      'a shared field and a page field referencing each other',
      { 11: formData(5), 5: formData(11) },
      [5, 11],
    ],
    [
      'a shared container referencing a page field referencing its child',
      { 10: formData(5), 5: formData(11) },
      [5, 10],
    ],
  ])('detects %s', (_name, conditions, expectedInvalid) => {
    const { isInvalid } = setup(conditions)
    const invalid = [1, 2, 3, 4, 5, 10, 11].filter(isInvalid)
    expect(invalid).toEqual(expectedInvalid)
  })

  test.each([
    ['a field referencing a sibling', { 3: formData(4) }],
    ['a container referencing a field outside of it', { 2: formData(5) }],
    ['a chain without cycle', { 3: formData(4), 4: formData(5) }],
    ['a condition without form data', { 3: condition("get('user.id')") }],
  ])('allows %s', (_name, conditions) => {
    const { isInvalid } = setup(conditions)
    expect([1, 2, 3, 4, 5, 10, 11].filter(isInvalid)).toEqual([])
  })

  test('excludes the form elements which would create a cycle', () => {
    // Field 5 depends on field 3, which is inside the column.
    const { store, applicationContext, page } = setup({ 5: formData(3) })
    expect(
      getVisibilityCycleElementIds(
        store,
        applicationContext,
        page.elementMap[2],
        [3, 4, 5, 11]
      )
    ).toEqual(new Set([3, 5]))
  })
})
