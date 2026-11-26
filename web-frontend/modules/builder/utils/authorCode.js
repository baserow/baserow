import { trueValues } from '@baserow/modules/core/utils/constants'
import { previewSharesEditorHostname } from '@baserow/modules/builder/utils/preview'

/**
 * "Author code" is code written by an application's editors: custom
 * JavaScript, external scripts, head HTML, HTML element scripts and IFrame
 * embeds. On an editor hostname it could act as the logged-in user, because
 * cookies are scoped by hostname. Use the `$isAuthorCodeRestricted` plugin to
 * ask whether it is restricted on the current page.
 */

/**
 * Nuxt leaves a word such as "no" or "off" as a non-empty string, so the
 * setting is only on for a value that means true.
 *
 * @param {object} publicConfig The public runtime config.
 * @returns {boolean} Whether the instance lets author code run on the editor's
 *   hostname outside the editor.
 */
export const isPreviewSecurityRelaxed = (publicConfig) =>
  trueValues.includes(
    String(publicConfig.builderDangerousRelaxPreviewSecurity ?? '')
      .trim()
      .toLowerCase()
  )

/**
 * Whether author code must be kept from acting as the logged-in user.
 *
 * That is always the case in the editor. An application page is restricted
 * when it is served on an editor hostname, unless the instance relaxes it. This
 * follows the hostname the page is served on, not the configured URLs: by
 * default the editor's hostname serves Preview, and it also serves published
 * applications by id. An application on its own hostname is never restricted.
 *
 * @param {object} options
 * @param {string} options.mode The application mode: editing, preview or public.
 * @param {boolean} options.onEditorHostname Whether the page is served on an
 *   editor hostname. Anything but `false` counts as yes.
 * @param {object} options.publicConfig The public runtime config.
 * @returns {boolean} Whether author code is restricted.
 */
export const isAuthorCodeRestricted = ({
  mode,
  onEditorHostname,
  publicConfig,
}) => {
  if (mode !== 'preview' && mode !== 'public') {
    return true
  }
  return onEditorHostname !== false && !isPreviewSecurityRelaxed(publicConfig)
}

/**
 * Whether Preview will restrict author code, for the editor to tell the user.
 *
 * @param {object} publicConfig The public runtime config.
 * @returns {boolean} Whether Preview restricts author code.
 */
export const isPreviewAuthorCodeRestricted = (publicConfig) =>
  previewSharesEditorHostname(publicConfig) &&
  !isPreviewSecurityRelaxed(publicConfig)
