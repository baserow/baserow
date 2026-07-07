import { TestApp } from '@baserow/test/helpers/testApp'
import RowCardFieldFormula from '@baserow/modules/database/components/card/RowCardFieldFormula'

describe('FormulaFieldType.getGroupByComponent()', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const registry = () => testApp._app.$registry

  test('delegates to the underlying result field type, not RowCardFieldFormula', () => {
    const formulaType = registry().get('field', 'formula')
    const numberFormula = { formula_type: 'number', number_decimal_places: 0 }
    const numberFieldType = registry().get('field', 'number')

    const component = formulaType.getGroupByComponent(numberFormula)

    expect(component).toBe(numberFieldType.getGroupByComponent(numberFormula))
    // RowCardFieldFormula requires a `row` prop the group-by banner does not pass, so
    // it must not be used to render the group header value.
    expect(component).not.toBe(RowCardFieldFormula)
  })

  test('a boolean formula groups via the boolean group-value component', () => {
    const formulaType = registry().get('field', 'formula')
    const booleanFormula = { formula_type: 'boolean' }
    const booleanFieldType = registry().get('field', 'boolean')

    expect(formulaType.getGroupByComponent(booleanFormula)).toBe(
      booleanFieldType.getGroupByComponent(booleanFormula)
    )
  })
})
