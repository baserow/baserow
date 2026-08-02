import { resolveFormula } from '@baserow/modules/core/formula'
import RuntimeFormulaContext from '@baserow/modules/core/runtimeFormulaContext'

/**
 * Resolves a button field's URL formula against a row, client-side. Returns
 * the resolved text as the user built it, so it can also be shown as the
 * button's label. Returns an empty string when the formula is empty or cannot
 * be resolved.
 */
export function resolveButtonUrl($registry, field, row, fields) {
  const formulaObject = field.url_formula
  if (!formulaObject?.formula) {
    return ''
  }
  const formulaFunctions = {
    get: (name) => $registry.get('runtimeFormulaFunction', name),
  }
  const runtimeFormulaContext = new Proxy(
    new RuntimeFormulaContext($registry.getAll('databaseDataProvider'), {
      row,
      fields,
    }),
    {
      get(target, prop) {
        return target.get(prop)
      },
    }
  )
  const result = resolveFormula(
    formulaObject,
    formulaFunctions,
    runtimeFormulaContext
  )
  if (result === null || result === undefined) {
    return ''
  }
  return `${result}`.trim()
}

/**
 * Percent-encodes the whitespace in a resolved URL. Row values often contain
 * spaces and browsers accept them by encoding, but our URL validation does
 * not. Only whitespace is touched: anything more would mangle the URL
 * structure the formula builds, and would double-encode a value the user
 * already escaped with `encode_uri_component()`.
 */
export function encodeUrlWhitespace(url) {
  return url.replace(/\s/g, (character) => encodeURIComponent(character))
}

/**
 * The protocols a button is allowed to navigate to. Mirrors the builder's
 * `ALLOWED_LINK_PROTOCOLS`, kept here so the database module does not depend
 * on the builder module.
 */
export const ALLOWED_BUTTON_URL_PROTOCOLS = [
  'ftp:',
  'ftps:',
  'ftpes:',
  'http:',
  'https:',
  'mailto:',
  'sftp:',
  'sms:',
  'tel:',
]

/**
 * Returns the URL when its protocol is allowed, and an empty string when it is
 * not. A URL without a protocol is relative and passes through. This is what
 * keeps a `javascript:` URL built by a formula from being navigated to.
 */
export function urlWithAllowedProtocol(url) {
  if (!/^[A-Za-z]+:/.test(url)) {
    return url
  }
  const lowerCased = url.toLowerCase()
  const allowed = ALLOWED_BUTTON_URL_PROTOCOLS.some((protocol) =>
    lowerCased.startsWith(protocol)
  )
  return allowed ? url : ''
}
