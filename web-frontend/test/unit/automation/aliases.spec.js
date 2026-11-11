import { parseAliases } from '@baserow/modules/automation/utils/aliases'

describe('parseAliases', () => {
  test('splits a comma-separated locale string into trimmed terms', () => {
    expect(parseAliases('loop, for loop ,repeat,  iterate')).toEqual([
      'loop',
      'for loop',
      'repeat',
      'iterate',
    ])
  })

  test('keeps a single term as is', () => {
    expect(parseAliases('while loop')).toEqual(['while loop'])
  })

  test('drops empty terms', () => {
    expect(parseAliases('loop,, ,repeat,')).toEqual(['loop', 'repeat'])
  })

  test('returns no terms for an empty or missing string', () => {
    expect(parseAliases('')).toEqual([])
    expect(parseAliases('   ')).toEqual([])
    expect(parseAliases(null)).toEqual([])
    expect(parseAliases(undefined)).toEqual([])
  })
})
