import { loadAllFeatureBundles } from '@baserow/modules/core/utils/featureBundles'

/** Initialize features after every plugin has registered its bundle extensions. */
export default defineNuxtPlugin({
  name: 'feature-bundle-startup',
  enforce: 'post',
  async setup(app) {
    const lazyFeatures = app.$config.public.baserowFrontendLazyFeatures
    if (lazyFeatures === true || lazyFeatures === 'true') return
    await loadAllFeatureBundles(app)
  },
})
