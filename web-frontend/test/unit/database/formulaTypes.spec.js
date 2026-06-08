import {
  BaserowFormulaURLType,
  BaserowFormulaLinkType,
} from '@baserow/modules/database/formula/formulaTypes'

describe('formula URL types toHumanReadableString', () => {
  const app = {}
  const field = {}

  describe.each([
    ['BaserowFormulaURLType', new BaserowFormulaURLType({ app })],
    ['BaserowFormulaLinkType', new BaserowFormulaLinkType({ app })],
  ])('%s', (name, formulaType) => {
    test('returns an empty string for a null value', () => {
      expect(formulaType.toHumanReadableString(field, null)).toBe('')
    })

    test('returns an empty string for an undefined value', () => {
      expect(formulaType.toHumanReadableString(field, undefined)).toBe('')
    })

    test('formats a value with a label and url', () => {
      expect(
        formulaType.toHumanReadableString(field, {
          label: 'Baserow',
          url: 'https://baserow.io',
        })
      ).toBe('Baserow (https://baserow.io)')
    })

    test('returns the url when there is no label', () => {
      expect(
        formulaType.toHumanReadableString(field, {
          url: 'https://baserow.io',
        })
      ).toBe('https://baserow.io')
    })
  })

  test('BaserowFormulaURLType returns a plain string value as-is', () => {
    const formulaType = new BaserowFormulaURLType({ app })
    expect(formulaType.toHumanReadableString(field, 'https://baserow.io')).toBe(
      'https://baserow.io'
    )
  })
})
