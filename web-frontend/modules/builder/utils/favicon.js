import head from '@baserow/modules/core/head'

/**
 * The `key` values of the default favicon `<link>` tags defined in
 * `core/head.js`. unhead dedupes `link` tags by `key`, so reusing these keys is
 * what lets a builder's custom favicon override the defaults instead of being
 * appended alongside them. Deriving the keys from `head.js` (rather than
 * hardcoding them here) guarantees the two stay in sync.
 *
 * @returns {string[]} the `key` of every default favicon link.
 */
export const getDefaultFaviconKeys = () =>
  head.link.filter((link) => link.rel === 'icon').map((link) => link.key)

/**
 * Returns the favicon `<link>` tags for a builder application.
 *
 * When the builder has a custom favicon uploaded, one overriding link is
 * returned per default favicon key, all pointing at the custom file, so the
 * custom favicon wins regardless of which size the browser decides to use.
 *
 * When no custom favicon is set, `null` is returned so that the defaults from
 * `core/head.js` remain in place untouched.
 *
 * @param {object} builder the builder application.
 * @returns {object[]|null} the override favicon links, or `null` to keep the
 *   defaults.
 */
export const getCustomFaviconLinks = (builder) => {
  if (!builder.favicon_file?.url) {
    return null
  }
  return getDefaultFaviconKeys().map((key) => ({
    key,
    rel: 'icon',
    type: builder.favicon_file.mime_type,
    href: builder.favicon_file.url,
  }))
}
