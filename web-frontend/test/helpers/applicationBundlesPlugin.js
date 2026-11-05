import { loadAllApplicationBundles } from '@baserow/modules/core/utils/applicationBundles'

/** Keep TestApp's existing full-registry fixtures while production loads on demand. */
export default defineNuxtPlugin({
  name: 'application-bundle-test-fixtures',
  enforce: 'post',
  async setup(app) {
    await loadAllApplicationBundles(app)
  },
})
