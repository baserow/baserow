import { TestApp } from '@baserow/test/helpers/testApp'
import {
  getVisibilityCycleElementIds,
  hasInvalidVisibilityCondition,
} from '@baserow/modules/builder/utils/visibilityCondition'

vi.mock('@baserow/modules/builder/utils/visibilityCondition', () => ({
  getVisibilityCycleElementIds: vi.fn(() => new Set()),
  hasInvalidVisibilityCondition: vi.fn(() => false),
}))

describe('Invalid visibility conditions', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    vi.clearAllMocks()
    hasInvalidVisibilityCondition.mockReturnValue(false)
    getVisibilityCycleElementIds.mockReturnValue(new Set())
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const element = {
    id: 2,
    type: 'heading',
    page_id: 1,
    value: { formula: "'Title'" },
    level: 1,
  }
  const applicationContext = { builder: { id: 1 }, workspace: {}, element }

  test('an element with an invalid visibility condition is in error', () => {
    const elementType = testApp.getRegistry().get('element', 'heading')
    expect(elementType.getErrorMessage(element, applicationContext)).toBe(null)

    hasInvalidVisibilityCondition.mockReturnValue(true)
    expect(elementType.getErrorMessage(element, applicationContext)).toBe(
      'elementType.errorInvalidVisibilityCondition'
    )
    expect(elementType.isInError(element, applicationContext)).toBe(true)
  })

  test('the visibility tab is in error', () => {
    const sidePanelType = testApp
      .getRegistry()
      .get('pageSidePanel', 'visibility')
    expect(sidePanelType.isInError(applicationContext)).toBe(false)

    hasInvalidVisibilityCondition.mockReturnValue(true)
    expect(sidePanelType.isInError(applicationContext)).toBe(true)
    expect(sidePanelType.getErrorMessage(applicationContext)).toBe(
      'pageSidePanelType.visibilityTabInError'
    )
    // Without a selected element, there is no condition to check.
    expect(sidePanelType.isInError({ builder: { id: 1 } })).toBe(false)
  })

  test('the data explorer omits the form elements which would create a cycle', () => {
    const dataProvider = testApp
      .getRegistry()
      .get('builderDataProvider', 'form_data')
    const field = (id) => ({
      id,
      type: 'input_text',
      page_id: 1,
      label: { formula: `'Field ${id}'` },
      default_value: { formula: '' },
      placeholder: { formula: '' },
    })
    const page = { id: 1, orderedElements: [field(3), field(4)] }
    vi.spyOn(dataProvider, 'formElementsInNamespacePath').mockReturnValue(
      page.orderedElements
    )
    getVisibilityCycleElementIds.mockReturnValue(new Set([3]))
    const context = { page, element: { id: 2, page_id: 1 } }

    // Other formulas can reference any form element.
    expect(Object.keys(dataProvider.getDataSchema(context).properties)).toEqual(
      ['3', '4']
    )
    expect(getVisibilityCycleElementIds).not.toHaveBeenCalled()

    expect(
      Object.keys(
        dataProvider.getDataSchema({ ...context, isVisibilityCondition: true })
          .properties
      )
    ).toEqual(['4'])
    expect(getVisibilityCycleElementIds).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ isVisibilityCondition: true }),
      context.element,
      [3, 4]
    )
  })
})
