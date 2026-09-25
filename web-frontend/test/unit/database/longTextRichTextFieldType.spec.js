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

  test('forms do not offer image upload, which needs a signed in user', () => {
    const components = fieldType.getFormViewFieldComponents(richField)
    expect(Object.values(components)[0].properties).toEqual({
      allowImageUpload: false,
    })
    const plain = fieldType.getFormViewFieldComponents(plainField)
    expect(Object.values(plain)[0].properties).toEqual({})
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

  test('drops image URLs from pasted plain text, which Baserow did not resolve', () => {
    expect(
      fieldType.prepareValueForPaste(
        richField,
        '![x][abc_def.png](https://evil.example.com/p.png)',
        null
      )
    ).toBe('![x][abc_def.png]')
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
