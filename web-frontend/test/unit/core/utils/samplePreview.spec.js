import { getSamplePreview } from '@baserow/modules/core/utils/samplePreview'

describe('getSamplePreview', () => {
  test('has nothing to show when no value is known', () => {
    expect(getSamplePreview(undefined)).toBeNull()
  })

  test('tells a known empty value apart from an unknown one', () => {
    expect(getSamplePreview(null)).toStrictEqual({ kind: 'empty' })
    expect(getSamplePreview('')).toStrictEqual({ kind: 'empty' })
    expect(getSamplePreview('  \n ')).toStrictEqual({ kind: 'empty' })
  })

  test('keeps falsy values that are real values', () => {
    expect(getSamplePreview(0)).toStrictEqual({ kind: 'text', text: '0' })
    expect(getSamplePreview(false)).toStrictEqual({
      kind: 'text',
      text: 'false',
    })
  })

  test('summarises lists and objects', () => {
    expect(getSamplePreview([1, 2, 3])).toStrictEqual({
      kind: 'items',
      count: 3,
    })
    expect(getSamplePreview([])).toStrictEqual({ kind: 'items', count: 0 })
    expect(getSamplePreview({ a: 1, b: 2 })).toStrictEqual({
      kind: 'fields',
      count: 2,
    })
  })

  test('puts text on one line and cuts it when too long', () => {
    expect(getSamplePreview('Hello\n  world')).toStrictEqual({
      kind: 'text',
      text: 'Hello world',
    })
    expect(getSamplePreview('abcdef', 3)).toStrictEqual({
      kind: 'text',
      text: 'abc…',
    })
  })
})
