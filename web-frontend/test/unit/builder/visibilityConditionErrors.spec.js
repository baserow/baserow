import { TestApp } from '@baserow/test/helpers/testApp'

describe('Invalid visibility conditions', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const element = {
    id: 2,
    type: 'heading',
    page_id: 1,
    _: { elementNamespacePath: [] },
    value: { formula: "'Title'" },
    level: 1,
    visibility_condition: { formula: "'Visible'", mode: 'simple' },
  }
  const inaccessibleInput = {
    id: 3,
    type: 'input_text',
    page_id: 1,
    _: { elementNamespacePath: [] },
    label: { formula: "'Inside column'" },
    default_value: { formula: '' },
    placeholder: { formula: '' },
  }
  const accessibleInput = {
    id: 4,
    type: 'input_text',
    page_id: 1,
    _: { elementNamespacePath: [] },
    label: { formula: "'Outside column'" },
    default_value: { formula: '' },
    placeholder: { formula: '' },
  }
  const page = {
    id: 1,
    elementMap: { 2: element, 3: inaccessibleInput, 4: accessibleInput },
    orderedElements: [accessibleInput, element, inaccessibleInput],
    graph: {
      0: 4,
      2: { children: { 0: [3] } },
      3: {},
      4: { next: { '': [2] } },
    },
  }
  const applicationContext = {
    builder: { id: 1 },
    workspace: {},
    page,
    element,
  }

  test.each([
    ['an unknown function', 'unknown_function()'],
    ['an unavailable data provider', "get('unknown_provider.value')"],
    ['a form field inside the controlled column', "get('form_data.3')"],
  ])('the visibility tab is in error for %s', (_description, formula) => {
    const sidePanelType = testApp
      .getRegistry()
      .get('pageSidePanel', 'visibility')
    expect(sidePanelType.isInError(applicationContext)).toBe(false)

    const invalidContext = {
      ...applicationContext,
      element: {
        ...element,
        visibility_condition: { formula, mode: 'simple' },
      },
    }
    expect(sidePanelType.isInError(invalidContext)).toBe(true)
    expect(sidePanelType.getErrorMessage(invalidContext)).toBe(
      'pageSidePanelType.visibilityTabInError'
    )
    expect(sidePanelType.isInError({ builder: { id: 1 } })).toBe(false)
  })

  test('an element with an invalid visibility condition is in error', () => {
    const elementType = testApp.getRegistry().get('element', 'heading')
    expect(elementType.isInError(element, applicationContext)).toBe(false)

    const invalidElement = {
      ...element,
      visibility_condition: { formula: "get('form_data.3')", mode: 'simple' },
    }
    expect(
      elementType.getErrorMessage(invalidElement, {
        ...applicationContext,
        element: invalidElement,
      })
    ).toBe('elementType.errorInvalidVisibilityCondition')
  })

  test('the visibility tab allows an available form-data reference', () => {
    const sidePanelType = testApp
      .getRegistry()
      .get('pageSidePanel', 'visibility')
    const context = {
      ...applicationContext,
      element: {
        ...element,
        visibility_condition: { formula: "get('form_data.4')", mode: 'simple' },
      },
    }

    expect(sidePanelType.isInError(context)).toBe(false)
  })
})
