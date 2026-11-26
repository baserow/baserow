import {
  isAuthorCodeRestricted,
  isPreviewAuthorCodeRestricted,
} from '@baserow/modules/builder/utils/authorCode'

/**
 * The one check the editor, Preview and published applications share to decide
 * whether code written by an application's editors is restricted.
 *
 * - `$isAuthorCodeRestricted()`: whether it is restricted on this page,
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
        isAuthorCodeRestricted: () =>
          isAuthorCodeRestricted({
            isWebFrontendHostname: nuxtApp.$isWebFrontendHostname,
            publicConfig: config.public,
          }),
        previewRestrictsAuthorCode: () =>
          isPreviewAuthorCodeRestricted(config.public),
      },
    }
  },
})
