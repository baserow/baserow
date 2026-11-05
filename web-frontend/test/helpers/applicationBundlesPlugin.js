import { loadAllFeatureBundles } from '@baserow/modules/core/utils/featureBundles'

/** Keep TestApp's existing full-registry fixtures while production loads on demand. */
export default defineNuxtPlugin({
  name: 'feature-bundle-test-fixtures',
  enforce: 'post',
  async setup(app) {
    await loadAllFeatureBundles(app)
  },
})
