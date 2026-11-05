/**
 * Production Nuxt configuration
 *
 * We use a direct import rather than `extends: ['./nuxt.config.base.ts']` because
 * Nuxt 3's `extends` mechanism is designed for Nuxt layers (directories containing
 * their own nuxt.config.ts, app.vue, pages/, etc.), not for importing individual
 * config files directly.
 *
 * When pointing `extends` to a .ts file, Nuxt shows:
 *   "WARN Cannot extend config from ./nuxt.config.base.ts"
 *
 * By using a standard ES module import/export, we achieve the same result reliably.
 */

import baseConfig from './nuxt.config.base.ts'
import { createPublicRuntimeBundle } from './publicRuntimeBundle.js'
import { createApplicationFeatureBundles } from './applicationFeatureBundles.js'
export default {
  ...baseConfig,
  hooks: {
    /**
     * Group the app entry and published Builder page's static dependencies into
     * a shared runtime chunk. Splitting application features into lazy bundles
     * otherwise creates many requests for small shared modules on public pages.
     * The helper follows static imports only, so dynamically imported editor UI
     * and optional features remain outside this group and load when requested.
     * Exclusive application dependencies get one named group per application type;
     * cross-application dependencies remain shared. This changes the production
     * client build; server bundling is unchanged.
     */
    'vite:extendConfig'(config, { isClient }) {
      if (!isClient) return
      const { plugin, group } = createPublicRuntimeBundle()
      const features = createApplicationFeatureBundles()
      config.plugins.push(plugin, features.plugin)
      config.build.rollupOptions.output.codeSplitting = {
        groups: [group, ...features.groups],
      }
    },
    /**
     * Keep deferred features from downloading before they are needed. A dynamic
     * import creates a separate chunk, but Nuxt can still prefetch that chunk
     * and its static dependencies even when the page never renders the feature.
     * Disable speculative prefetch for application/editor bundles, optional
     * graphs and collection controls, and the session-cookie domain parser.
     * Walk their static imports too, since those chunks can also be prefetched
     * independently. Only the prefetch flag changes: SSR preloads remain enabled
     * for components actually rendered, and explicit imports still load normally.
     */
    'build:manifest'(manifest) {
      const visited = new Set()
      const deferPrefetch = (id) => {
        if (visited.has(id) || !manifest[id]) return
        visited.add(id)
        manifest[id].prefetch = false
        for (const dependency of manifest[id].imports || []) {
          deferPrefetch(dependency)
        }
      }
      for (const id of Object.keys(manifest)) {
        if (
          /\/(?:\w+(?:Application|Authentication)|elementEditorBundle|authoringBundle|editorRenderingBundle|collectionRefinementsBundle|onboarding(?:Rendering)?Bundle|(?:application|database|dashboard|automation|builder|agent)Bundle)\.js$|\/GraphElement\.vue$/.test(
            id
          ) ||
          /^(?:(?:database|builder|dashboard|automation|agent)-application|application-shared|onboarding(?:-rendering|-shared)?)$/.test(
            manifest[id].name || ''
          ) ||
          /(?:^|\/)node_modules\/tldjs\//.test(id)
        ) {
          deferPrefetch(id)
        }
      }
    },
  },
  nitro: {
    ...baseConfig.nitro,
    // Precompress the static assets at build time, so that they're served with
    // brotli or gzip even when no compressing reverse proxy is in front.
    compressPublicAssets: { gzip: true, brotli: true },
  },
  sourcemap: {
    server: true,
    client: true,
  },
}
