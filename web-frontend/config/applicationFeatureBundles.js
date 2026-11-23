const applicationTypes = [
  'database',
  'builder',
  'dashboard',
  'automation',
  'agent',
]

/**
 * Group each application's exclusive static graph into a named client bundle.
 * Dependencies used by several applications stay in a deferred shared group,
 * separate from the shell's shared helpers. This prevents the bundler from
 * combining a tiny sidebar dependency with all shared editor UI. Opening Dashboard
 * cannot download Database just because both import the same helper. Dynamic
 * imports remain lazy. Metadata and shell dependencies stay outside feature
 * groups so sidebar icons cannot cause a feature download at startup. Core
 * components stay outside application groups too: settings and other core pages
 * can reuse them without downloading shared application editors. The
 * higher-priority public runtime group stays shared. Dependencies shared with onboarding get their
 * own small group, so an importer used by Database cannot download every onboarding
 * form, and onboarding metadata cannot download the full Grid renderer.
 */
export function createApplicationFeatureBundles() {
  const featureTypes = [
    ...applicationTypes,
    'onboarding',
    'onboarding-rendering',
  ]
  const owners = new Map()
  const startupModules = new Set()
  return {
    plugin: {
      name: 'baserow-application-feature-bundles',
      buildEnd(error) {
        if (error) return
        const visit = (id, type) => {
          if (!owners.has(id)) owners.set(id, new Set())
          if (owners.get(id).has(type)) return
          owners.get(id).add(type)
          for (const dependency of this.getModuleInfo(id)?.importedIds || []) {
            visit(dependency, type)
          }
        }
        const visitStartup = (id) => {
          if (startupModules.has(id)) return
          startupModules.add(id)
          for (const dependency of this.getModuleInfo(id)?.importedIds || []) {
            visitStartup(dependency)
          }
        }
        for (const id of this.getModuleIds()) {
          if (
            /\/plugin(?:Metadata|Authentication)\.js$/.test(id) ||
            (id.includes('/modules/core/') &&
              !/\/(?:onboardingBundle\.js|components\/onboarding\/|pages\/onboarding\.vue)/.test(
                id
              )) ||
            (id.includes('virtual:nuxt:') && id.endsWith('app.vue')) ||
            /\/modules\/(?:core|baserow_premium|baserow_enterprise)\/pluginApplication\.js$/.test(
              id
            )
          ) {
            visitStartup(id)
          }
          // Keep route components in their normal chunks. Combining a route with
          // feature registration entries can snapshot its default export before
          // initialization during Nitro's server rebundling.
          for (const type of featureTypes) {
            if (
              (type === 'onboarding' && id.endsWith('/onboardingBundle.js')) ||
              (type === 'onboarding-rendering' &&
                id.endsWith('/onboardingRenderingBundle.js')) ||
              id.endsWith(`/modules/${type}/applicationBundle.js`) ||
              (/\/modules\/baserow_(?:premium|enterprise)\//.test(id) &&
                id.endsWith(`/${type}Bundle.js`))
            ) {
              visit(id, type)
            }
          }
        }
      },
    },
    groups: [
      ...featureTypes.map((type) => ({
        name: applicationTypes.includes(type) ? `${type}-application` : type,
        priority: 90,
        // The graph above already selects dependencies; recursive assignment would
        // pull excluded metadata and shared helpers back into the feature chunk.
        includeDependenciesRecursively: false,
        test: (id) =>
          !startupModules.has(id) &&
          owners.get(id)?.size === 1 &&
          owners.get(id).has(type),
      })),
      {
        name: 'onboarding-shared',
        priority: 85,
        includeDependenciesRecursively: false,
        test: (id) =>
          !startupModules.has(id) &&
          owners.get(id)?.has('onboarding') &&
          owners.get(id)?.size > 1,
      },
      {
        name: 'application-shared',
        priority: 80,
        includeDependenciesRecursively: false,
        test: (id) =>
          !startupModules.has(id) &&
          !owners.get(id)?.has('onboarding') &&
          owners.get(id)?.size > 1,
      },
    ],
  }
}
