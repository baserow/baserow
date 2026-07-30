import {
  PARSE_TREE_CACHE_MAX_SIZE,
  resolveFormula,
} from '@baserow/modules/core/formula'
import parseBaserowFormula from '@baserow/modules/core/formula/parser/parser'

vi.mock(
  '@baserow/modules/core/formula/parser/parser',
  async (importOriginal) => {
    const actual = await importOriginal()
    return { default: vi.fn((formula) => actual.default(formula)) }
  }
)

// Every test uses its own formula strings, because the cache is module level
// and therefore shared across the tests in this file.
const literal = (value) => ({ formula: `'${value}'`, mode: 'simple' })

const resolve = (formulaCtx) => resolveFormula(formulaCtx, {}, {})

describe('resolveFormula parse tree cache', () => {
  beforeEach(() => {
    parseBaserowFormula.mockClear()
  })

  test('the same formula is only parsed once', () => {
    const formulaCtx = literal('same')
    expect(resolve(formulaCtx)).toBe('same')
    expect(resolve(formulaCtx)).toBe('same')
    expect(resolve({ ...formulaCtx })).toBe('same')
    expect(parseBaserowFormula).toHaveBeenCalledTimes(1)
  })

  test('distinct formulas are parsed separately', () => {
    expect(resolve(literal('first'))).toBe('first')
    expect(resolve(literal('second'))).toBe('second')
    expect(parseBaserowFormula).toHaveBeenCalledTimes(2)
  })

  test('raw formulas never reach the parser', () => {
    const raw = { formula: 'https://example.com?x=(1', mode: 'raw' }
    expect(resolve(raw)).toBe('https://example.com?x=(1')
    expect(parseBaserowFormula).not.toHaveBeenCalled()
  })

  test('an unparseable formula resolves to null and is not cached', () => {
    const broken = { formula: 'concat(broken', mode: 'simple' }
    expect(resolve(broken)).toBe(null)
    expect(resolve(broken)).toBe(null)
    // Nothing is stored when parsing throws, so the second call parses again.
    expect(parseBaserowFormula).toHaveBeenCalledTimes(2)
  })

  test('a formula that keeps being used is not evicted', () => {
    const hot = literal('lru-hot')
    expect(resolve(hot)).toBe('lru-hot')

    // Fill the cache, touching the hot formula along the way. Eviction is
    // least-recently-used, so the cold fillers go first and the hot one stays.
    for (let i = 0; i < PARSE_TREE_CACHE_MAX_SIZE; i++) {
      resolve(literal(`lru-filler-${i}`))
      resolve(hot)
    }

    parseBaserowFormula.mockClear()
    expect(resolve(hot)).toBe('lru-hot')
    expect(parseBaserowFormula).not.toHaveBeenCalled()
  })

  test('the oldest entry is evicted once the cache is full', () => {
    const first = literal('evict-me')
    expect(resolve(first)).toBe('evict-me')

    // Fill the cache with enough distinct formulas to push the first one out.
    for (let i = 0; i < PARSE_TREE_CACHE_MAX_SIZE; i++) {
      resolve(literal(`evict-filler-${i}`))
    }

    parseBaserowFormula.mockClear()
    expect(resolve(first)).toBe('evict-me')
    expect(parseBaserowFormula).toHaveBeenCalledTimes(1)
  })
})
