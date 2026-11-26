import { trueValues } from '@baserow/modules/core/utils/constants'
import { previewSharesWebFrontendHostname } from '@baserow/modules/builder/utils/preview'

/**
 * "Author code" is code written by an application's editors: custom
 * JavaScript, external scripts, head HTML, HTML element scripts and IFrame
 * embeds. On a web frontend hostname it could act as the logged-in user,
 * because cookies are scoped by hostname. Use the `$isAuthorCodeRestricted` plugin to
 * ask whether it is restricted on the current page.
 */

/**
 * Nuxt leaves a word such as "no" or "off" as a non-empty string, so the
 * setting is only on for a value that means true.
 *
 * @param {object} publicConfig The public runtime config.
 * @returns {boolean} Whether the instance lets author code run on a web
 *   frontend hostname.
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
 * Author code is restricted when the current page uses the main web frontend
 * hostname or an additional configured web frontend hostname, unless the
 * instance relaxes this restriction. This applies regardless of the page mode.
 *
 * @param {object} options
 * @param {boolean} options.isWebFrontendHostname Whether the current page uses
 *   a configured web frontend hostname. Anything but `false` counts as yes.
 * @param {object} options.publicConfig The public runtime config.
 * @returns {boolean} Whether author code is restricted.
 */
export const isAuthorCodeRestricted = ({
  isWebFrontendHostname,
  publicConfig,
}) => isWebFrontendHostname !== false && !isPreviewSecurityRelaxed(publicConfig)

/**
 * Whether Preview will restrict author code, for the editor to tell the user.
 *
 * @param {object} publicConfig The public runtime config.
 * @returns {boolean} Whether Preview restricts author code.
 */
export const isPreviewAuthorCodeRestricted = (publicConfig) =>
  previewSharesWebFrontendHostname(publicConfig) &&
  !isPreviewSecurityRelaxed(publicConfig)
