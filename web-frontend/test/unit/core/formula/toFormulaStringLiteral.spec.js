import {
  resolveFormula,
  toFormulaStringLiteral,
} from '@baserow/modules/core/formula'

describe('toFormulaStringLiteral', () => {
  it.each([
    ['plain text', 'Price', "'Price'"],
    ['an empty string', '', "''"],
    ['a single quote', "it's", "'it\\'s'"],
    ['a backslash', 'a\\b', "'a\\\\b'"],
    ['a trailing backslash', 'a\\', "'a\\\\'"],
    ['an escaped quote', "a\\'b", "'a\\\\\\'b'"],
    ['double quotes', 'say "hi"', '\'say "hi"\''],
  ])('quotes %s', (_, text, literal) => {
    expect(toFormulaStringLiteral(text)).toBe(literal)
  })

  it.each([
    'Price',
    'Column 3',
    "it's",
    'a\\',
    "a\\'b",
    '\\\\',
    "get('x')",
    'say "hi"',
    'line\nbreak',
  ])('resolves back to the original text for %j', (text) => {
    const formulaCtx = {
      formula: toFormulaStringLiteral(text),
      mode: 'simple',
    }

    expect(resolveFormula(formulaCtx, {}, {})).toBe(text)
  })
})
