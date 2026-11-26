import {
  isAuthorCodeRestricted,
  isPreviewAuthorCodeRestricted,
} from '@baserow/modules/builder/utils/authorCode'

/**
 * The one check the editor, Preview and published applications share to decide
 * whether code written by an application's editors is restricted.
 *
 * - `$isAuthorCodeRestricted(mode)`: whether it is restricted on this page,
 *   where `mode` is the application mode (editing, preview or public).
 * - `$previewRestrictsAuthorCode()`: whether Preview will restrict it, for the
 *   editor to tell the user.
 */
export default defineNuxtPlugin({
  name: 'builder-author-code',
  dependsOn: ['is-web-frontend-hostname'],
  setup(nuxtApp) {
    const config = useRuntimeConfig()

    return {
      provide: {
        isAuthorCodeRestricted: (mode) =>
          isAuthorCodeRestricted({
            mode,
            onEditorHostname: nuxtApp.$isWebFrontendHostname,
            publicConfig: config.public,
          }),
        previewRestrictsAuthorCode: () =>
          isPreviewAuthorCodeRestricted(config.public),
      },
    }
  },
})
