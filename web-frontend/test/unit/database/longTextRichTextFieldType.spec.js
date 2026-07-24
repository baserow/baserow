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

  const resolveComponent = async (component) =>
    component.__asyncLoader ? await component.__asyncLoader() : component

  test('resolves the rich text components when the flag is enabled', async () => {
    expect(fieldType.getGridViewFieldComponent(richField)).toBe(
      GridViewFieldRichText
    )
    expect(fieldType.getFunctionalGridViewFieldComponent(richField)).toBe(
      FunctionalGridViewFieldRichText
    )
    expect(
      await resolveComponent(fieldType.getRowEditFieldComponent(richField))
    ).toBe(RowEditFieldRichText)
    expect(fieldType.getCardComponent(richField)).toBe(RowCardFieldRichText)
    expect(
      await resolveComponent(fieldType.getRowHistoryEntryComponent(richField))
    ).toBe(RowHistoryFieldRichText)
  })

  test('resolves the plain components when the flag is disabled', async () => {
    expect(fieldType.getGridViewFieldComponent(plainField)).toBe(
      GridViewFieldLongText
    )
    expect(fieldType.getFunctionalGridViewFieldComponent(plainField)).toBe(
      FunctionalGridViewFieldLongText
    )
    expect(
      await resolveComponent(fieldType.getRowEditFieldComponent(plainField))
    ).toBe(RowEditFieldLongText)
  })

  test('forms reuse the rich row edit component', async () => {
    const components = fieldType.getFormViewFieldComponents(richField)
    const defaultComponent = Object.values(components)[0]
    expect(await resolveComponent(defaultComponent.component)).toBe(
      RowEditFieldRichText
    )
  })

  test('rich text fields cannot be grouped by', () => {
    expect(fieldType.getCanGroupByInView(richField)).toBe(false)
    expect(fieldType.getCanGroupByInView(plainField)).toBe(true)
  })

  test('preserves repeated blank lines when pasting plain text into rich text', () => {
    const copiedValue = fieldType.prepareRichValueForCopy(
      plainField,
      'ciao\n\n\n\nmiao'
    )

    expect(
      fieldType.prepareValueForPaste(richField, 'ciao\n\n\n\nmiao', copiedValue)
    ).toBe('ciao\n\n&nbsp;\n\n&nbsp;\n\n&nbsp;\n\nmiao')
  })

  test('keeps a single plain text newline as a Markdown line break', () => {
    const copiedValue = fieldType.prepareRichValueForCopy(
      plainField,
      'ciao\nmiao'
    )

    expect(
      fieldType.prepareValueForPaste(richField, 'ciao\nmiao', copiedValue)
    ).toBe('ciao  \nmiao')
  })

  test('keeps copied rich Markdown unchanged', () => {
    const markdown = '# Heading\n\nA  \nB'
    const copiedValue = fieldType.prepareRichValueForCopy(richField, markdown)

    expect(
      fieldType.prepareValueForPaste(richField, markdown, copiedValue)
    ).toBe(markdown)
  })

  test('strips empty-paragraph sentinels when pasting rich into plain text', () => {
    const markdown = 'alpha\n\nbeta\n\n&nbsp;\n\ngamma'
    const copiedValue = fieldType.prepareRichValueForCopy(richField, markdown)

    expect(
      fieldType.prepareValueForPaste(plainField, markdown, copiedValue)
    ).toBe('alpha\nbeta\n\ngamma')
  })

  test('undoes Markdown hard breaks when pasting rich into plain text', () => {
    const markdown = 'ciao  \nmiao'
    const copiedValue = fieldType.prepareRichValueForCopy(richField, markdown)

    expect(
      fieldType.prepareValueForPaste(plainField, markdown, copiedValue)
    ).toBe('ciao\nmiao')
  })

  test('leaves plain-source clipboard untouched when pasting into plain text', () => {
    const copiedValue = fieldType.prepareRichValueForCopy(
      plainField,
      'ciao\nmiao'
    )

    expect(
      fieldType.prepareValueForPaste(plainField, 'ciao\nmiao', copiedValue)
    ).toBe('ciao\nmiao')
  })
})
