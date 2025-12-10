/***
 * Injects two functions and a handler for use globally:
 * - $licenseHandler
 *     A class holding some helper methods to do with licenses and no state of it own.
 * - $hasFeature(FEATURE_STRING, OPTIONAL_WORKSPACE_ID) -> bool
 *     Returns if the current user has access to the feature instance-wide if no workspace
 *     is supplied otherwise for the workspace if an id is provided.
 * - $highestLicenseType() -> LicenseType or null
 *     Returns the highest instance wide license the user has active or null if they
 *     do not have one.
 */
import { LicenseHandler } from '@baserow_premium/handlers/license'

export default defineNuxtPlugin({
  name: 'license',
  dependsOn: ['store', 'bus'],
  async setup(nuxtApp) {
    const licenseHandler = new LicenseHandler(nuxtApp)

    licenseHandler.listenToBusEvents()

    return {
      provide: {
        licenseHandler,
        highestLicenseType:
          licenseHandler.highestInstanceWideLicenseType.bind(licenseHandler),
      },
    }
  },
})

/*export default function ({ app }, inject) {
  const licenseHandler = new LicenseHandler(app)
  licenseHandler.listenToBusEvents()
  inject('licenseHandler', licenseHandler)
  inject(
    'highestLicenseType',
    licenseHandler.highestInstanceWideLicenseType.bind(licenseHandler)
  )
}*/
