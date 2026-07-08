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
 * @param {String} previewPathPrefix The configured preview path prefix.
 * @returns {String} A resolved URL.
 */
export default function resolveElementUrl(
  element,
  builder,
  pages,
  resolveFormula,
  editorMode,
  previewPathPrefix = ''
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
    element.navigation_type,
    editorMode,
    previewPathPrefix
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
 * Prefixes an internal preview URL with the configured fixed preview path
 * prefix, if any.
 *
 * @param {String} resolvedUrl A URL which `resolveElementUrl` has generated.
 * @param {String} navigationType An element's `navigation_type` (custom / page).
 * @param {String} editorMode A builder application's editor mode.
 * @param {String} previewPathPrefix The configured preview path prefix.
 * @returns {String} The resolved URL.
 */
export function prefixInternalResolvedUrl(
  resolvedUrl,
  navigationType,
  editorMode,
  previewPathPrefix = ''
) {
  const normalizedPrefix = normalizePreviewPathPrefix(previewPathPrefix)

  // Only internal URLs rendered in preview mode need the preview path prefix.
  // Page navigation is always internal, while custom navigation is internal only
  // when it uses a root-relative URL.
  if (
    !resolvedUrl ||
    !normalizedPrefix ||
    editorMode !== 'preview' ||
    !(
      navigationType === 'page' ||
      (navigationType === 'custom' && resolvedUrl.startsWith('/'))
    )
  ) {
    return resolvedUrl
  }

  // Avoid prefixing URLs which already point inside the configured preview path.
  // The three forms cover the prefix itself, a nested path, and a query string
  // attached directly to the prefix.
  if (
    resolvedUrl === normalizedPrefix ||
    resolvedUrl.startsWith(`${normalizedPrefix}/`) ||
    resolvedUrl.startsWith(`${normalizedPrefix}?`)
  ) {
    return resolvedUrl
  }

  // Preserve the slash between the preview prefix and a root-level query string.
  if (resolvedUrl.startsWith('/?')) {
    return `${normalizedPrefix}/${resolvedUrl.slice(1)}`
  }

  // All remaining internal URLs are root-relative paths, so prepend the prefix.
  return `${normalizedPrefix}${resolvedUrl}`
}

export function normalizePreviewPathPrefix(previewPathPrefix) {
  if (!previewPathPrefix) {
    return ''
  }
  return `/${previewPathPrefix.split('/').filter(Boolean).join('/')}`
}
