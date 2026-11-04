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
export default {
  ...baseConfig,
  hooks: {
    'vite:extendConfig'(config, { isClient }) {
      if (!isClient) return
      const { plugin, group } = createPublicRuntimeBundle()
      config.plugins.push(plugin)
      config.build.rollupOptions.output.codeSplitting = { groups: [group] }
    },
    /**
     * Global registries reference feature entries without rendering them, and
     * session cookies only need the domain parser when they are set.
     * Nuxt otherwise prefetches their static dependencies even on login/public
     * pages. Keep SSR preloads intact for components actually rendered there.
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
          /\/(?:\w+Application|elementEditorBundle|authoringBundle|editorRenderingBundle|collectionRefinementsBundle)\.js$|\/GraphElement\.vue$/.test(
            id
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
