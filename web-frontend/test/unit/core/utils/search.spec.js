import {
  matchesQuery,
  splitHighlight,
} from '@baserow/modules/core/utils/search'

describe('search utils', () => {
  describe('matchesQuery', () => {
    test('matches the name case insensitively as a substring', () => {
      expect(matchesQuery('Dexter Industries', 1, 'dex')).toBe(true)
      expect(matchesQuery('Dexter Industries', 1, 'INDUS')).toBe(true)
      expect(matchesQuery('Dexter Industries', 1, 'acme')).toBe(false)
    })

    test('ignores surrounding whitespace in the query', () => {
      expect(matchesQuery('Dexter Industries', 1, '  dex  ')).toBe(true)
    })

    test('never matches with an empty query', () => {
      expect(matchesQuery('Dexter Industries', 1, '')).toBe(false)
      expect(matchesQuery('Dexter Industries', 1, '   ')).toBe(false)
    })

    test('matches numeric queries against the id by prefix', () => {
      expect(matchesQuery('Dexter Industries', 123, '12')).toBe(true)
      expect(matchesQuery('Dexter Industries', 123, '123')).toBe(true)
      expect(matchesQuery('Dexter Industries', 123, '23')).toBe(false)
    })

    test('numeric queries still match numbers in the name', () => {
      expect(matchesQuery('Q1 2025 Planning', 7, '2025')).toBe(true)
    })

    test('non numeric queries never match the id', () => {
      expect(matchesQuery('Dexter Industries', 123, '12a')).toBe(false)
    })
  })

  describe('splitHighlight', () => {
    test('returns a single unmatched segment for an empty query', () => {
      expect(splitHighlight('Dexter', '')).toEqual([
        { text: 'Dexter', matched: false },
      ])
    })

    test('returns a single unmatched segment when there is no match', () => {
      expect(splitHighlight('Dexter', 'acme')).toEqual([
        { text: 'Dexter', matched: false },
      ])
    })

    test('splits around a case insensitive match preserving casing', () => {
      expect(splitHighlight('Dexter Industries', 'dex')).toEqual([
        { text: 'Dex', matched: true },
        { text: 'ter Industries', matched: false },
      ])
    })

    test('highlights every occurrence', () => {
      expect(splitHighlight('Test workflow test', 'test')).toEqual([
        { text: 'Test', matched: true },
        { text: ' workflow ', matched: false },
        { text: 'test', matched: true },
      ])
    })

    test('segments concatenate back to the original text', () => {
      const text = 'Department Workflow'
      const segments = splitHighlight(text, 'de')
      expect(segments.map((segment) => segment.text).join('')).toBe(text)
    })

    test('keeps offsets aligned for characters that grow when lowercased', () => {
      const text = 'İstanbul HQ'
      const segments = splitHighlight(text, 'stan')
      expect(segments).toEqual([
        { text: 'İ', matched: false },
        { text: 'stan', matched: true },
        { text: 'bul HQ', matched: false },
      ])
      expect(segments.map((segment) => segment.text).join('')).toBe(text)
    })

    test('highlights everything that matchesQuery matches', () => {
      // `İ` lowercases to `i` plus a combining dot, so the search matches `i`
      // and the whole original character must be highlighted.
      expect(matchesQuery('İstanbul', 1, 'i')).toBe(true)
      expect(splitHighlight('İstanbul', 'i')).toEqual([
        { text: 'İ', matched: true },
        { text: 'stanbul', matched: false },
      ])
    })
  })
})
