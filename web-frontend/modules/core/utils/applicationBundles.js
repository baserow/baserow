// Application features use the same per-app lifecycle as other deferred features.
export {
  registerFeatureBundle as registerApplicationBundle,
  hasFeatureBundle as hasApplicationBundle,
  isFeatureBundleLoaded as isApplicationBundleLoaded,
  loadFeatureBundle as loadApplicationBundle,
  loadAllFeatureBundles as loadAllApplicationBundles,
  getFeatureComponent as getApplicationComponent,
} from '@baserow/modules/core/utils/featureBundles'
