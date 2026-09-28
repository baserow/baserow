export const BASEROW_FORMULA_MODES = ['raw', 'simple', 'advanced']

// The formats a surface can render the resolved value of a formula in. Plain
// is the implicit default: a formula object without a `format` key is plain,
// and the key is never set to plain.
export const BASEROW_FORMULA_FORMAT_PLAIN = 'plain'
export const BASEROW_FORMULA_FORMAT_MARKDOWN = 'markdown'
export const BASEROW_FORMULA_FORMATS = [
  BASEROW_FORMULA_FORMAT_PLAIN,
  BASEROW_FORMULA_FORMAT_MARKDOWN,
]
