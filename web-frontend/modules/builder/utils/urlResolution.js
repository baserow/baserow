import { compile } from 'path-to-regexp'
import {
  ALLOWED_LINK_PROTOCOLS,
  PAGE_PARAM_TYPE_VALIDATION_FUNCTIONS,
} from '@baserow/modules/builder/enums'
import { ensureString } from '@baserow/modules/core/utils/validator'
import { getUrlScheme } from '@baserow/modules/core/utils/url'

/**
 * Responsible for generating the data necessary to resolve an application builder
 * element URL. Used by LinkElement and LinkField to generate URLs, based on the
 * designer's navigation type / page / url choices.
 *
 * @param {Object} element The element's properties we'll use for generating the URL.
 * @param {Object} builder A builder application.
 * @param {Array} pages A list of pages of this application.
 * @param {Function} resolveFormula A resolveFormula function we'll use if the
 *  element has page parameters which need to be resolved.
 * @param {String} editorMode A builder application's editor mode.
 * @returns {String} A resolved URL.
 */
export default function resolveElementUrl(
  element,
  builder,
  pages,
  resolveFormula,
  editorMode
) {
  let resolvedUrl = ''
  if (element.navigation_type === 'page') {
    if (!isNaN(element.navigate_to_page_id)) {
      const page = pages.find(({ id }) => id === element.navigate_to_page_id)

      // The builder page list might be empty or the page has been deleted
      if (!page) {
        return resolvedUrl
      }

      const paramTypeMap = Object.fromEntries(
        page.path_params.map(({ name, type }) => [name, type])
      )

      const toPath = compile(page.path, { encode: encodeURIComponent })

      const pageParams = Object.fromEntries(
        element.page_parameters
          .filter(({ name }) => name in paramTypeMap)
          .map(({ name, value }) => [
            name,
            ensureString(
              PAGE_PARAM_TYPE_VALIDATION_FUNCTIONS[paramTypeMap[name]](
                resolveFormula(value)
              )
            ), // We ensure string here because toPath expect strings.
          ])
      )
      resolvedUrl = toPath(pageParams)
    }
  } else {
    resolvedUrl = ensureString(resolveFormula(element.navigate_to_url))
  }
  // Browsers strip leading C0 control characters and spaces before parsing
  // a URL, so ` javascript:` reads as relative here but still executes as
  // a script. Strip them before anything classifies this string.
  // eslint-disable-next-line no-control-regex
  resolvedUrl = resolvedUrl.replace(/^[\x00-\x20]+/, '')
  resolvedUrl = prefixInternalResolvedUrl(
    resolvedUrl,
    builder,
    element.navigation_type,
    editorMode
  )
  // Add query parameters if they exist
  if (element.query_parameters && element.query_parameters.length > 0) {
    const queryString = element.query_parameters
      .map(({ name, value }) => {
        if (!value) return null
        const resolvedValue = resolveFormula(value)
        if (!resolvedValue && String(resolvedValue) !== '0') return null
        return `${encodeURIComponent(name)}=${encodeURIComponent(
          resolvedValue
        )}`
      })
      .filter((param) => param !== null)
      .join('&')
    if (queryString) {
      resolvedUrl = `${resolvedUrl}?${queryString}`
    }
  }
  // Browsers ignore tab / LF / CR anywhere in a URL,
  // so `java\tscript:` is still `javascript:`.
  const scheme = getUrlScheme(resolvedUrl)
  if (scheme) {
    // Disallow unsupported protocols, e.g. `javascript:`
    return ALLOWED_LINK_PROTOCOLS.includes(scheme) ? resolvedUrl : ''
  }
  return resolvedUrl
}

/**
 * Responsible for prefixing a resolvedUrl with the builder application's preview
 * URI, if it meets certain conditions.
 *
 * @param {String} resolvedUrl A URL which `resolveElementUrl` has generated.
 * @param {Object} builder A builder application.
 * @param {String} navigationType An element's `navigation_type` (custom / page).
 * @param {String} editorMode A builder application's editor mode.
 * @returns {String} A URL we may have prefixed with the application's preview URI.
 */
export function prefixInternalResolvedUrl(
  resolvedUrl,
  builder,
  navigationType,
  editorMode
) {
  if (
    resolvedUrl &&
    editorMode === 'preview' &&
    (navigationType === 'page' ||
      (navigationType === 'custom' && resolvedUrl.startsWith('/')))
  ) {
    // Add prefix in preview mode for page navigation or custom URL starting with `/`
    return `/builder/${builder.id}/preview${resolvedUrl}`
  } else {
    return resolvedUrl
  }
}
