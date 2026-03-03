import { defineNuxtConfig } from 'nuxt/config'
import baseConfig from './nuxt.config.base.ts'

export default defineNuxtConfig({
  ...baseConfig,
  modules: [...(baseConfig.modules || []), '@nuxt/eslint'],
  devtools: { enabled: true },
  hooks: {
    // Prevent Nitro's devStorage from watching the entire repo root with
    // chokidar, which causes EMFILE on macOS in large monorepos / worktrees.
    // See https://github.com/nuxt/nuxt/issues/30481
    'nitro:config'(nitroConfig) {
      nitroConfig.devStorage ??= {}
      nitroConfig.devStorage['root'] = {
        driver: 'fs-lite',
        readOnly: true,
        base: nitroConfig.rootDir,
      }
    },
  },
})
