import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewFieldLongText from '@baserow/modules/database/components/view/grid/fields/GridViewFieldLongText'
import GridViewFieldRichText from '@baserow/modules/database/components/view/grid/fields/GridViewFieldRichText'
import FunctionalGridViewFieldLongText from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldLongText'
import FunctionalGridViewFieldRichText from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldRichText'
import RowEditFieldLongText from '@baserow/modules/database/components/row/RowEditFieldLongText'
import RowEditFieldRichText from '@baserow/modules/database/components/row/RowEditFieldRichText'
import RowCardFieldRichText from '@baserow/modules/database/components/card/RowCardFieldRichText'
import RowHistoryFieldRichText from '@baserow/modules/database/components/row/RowHistoryFieldRichText'

describe('LongTextFieldType rich text switching', () => {
  let testApp = null
  let fieldType = null

  beforeEach(() => {
    testApp = new TestApp()
    fieldType = testApp._app.$registry.get('field', 'long_text')
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const richField = { type: 'long_text', long_text_enable_rich_text: true }
  const plainField = { type: 'long_text', long_text_enable_rich_text: false }

  test('resolves the rich text components when the flag is enabled', () => {
    expect(fieldType.getGridViewFieldComponent(richField)).toBe(
      GridViewFieldRichText
    )
    expect(fieldType.getFunctionalGridViewFieldComponent(richField)).toBe(
      FunctionalGridViewFieldRichText
    )
    expect(fieldType.getRowEditFieldComponent(richField)).toBe(
      RowEditFieldRichText
    )
    expect(fieldType.getCardComponent(richField)).toBe(RowCardFieldRichText)
    expect(fieldType.getRowHistoryEntryComponent(richField)).toBe(
      RowHistoryFieldRichText
    )
  })

  test('resolves the plain components when the flag is disabled', () => {
    expect(fieldType.getGridViewFieldComponent(plainField)).toBe(
      GridViewFieldLongText
    )
    expect(fieldType.getFunctionalGridViewFieldComponent(plainField)).toBe(
      FunctionalGridViewFieldLongText
    )
    expect(fieldType.getRowEditFieldComponent(plainField)).toBe(
      RowEditFieldLongText
    )
  })

  test('forms reuse the rich row edit component', () => {
    const components = fieldType.getFormViewFieldComponents(richField)
    const defaultComponent = Object.values(components)[0]
    expect(defaultComponent.component).toBe(RowEditFieldRichText)
  })

  test('rich text fields cannot be grouped by', () => {
    expect(fieldType.getCanGroupByInView(richField)).toBe(false)
    expect(fieldType.getCanGroupByInView(plainField)).toBe(true)
  })
})
