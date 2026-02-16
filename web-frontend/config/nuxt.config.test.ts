/**
 * Test Nuxt configuration
 *
 * We use a direct import rather than `extends: ['./nuxt.config.base.ts']` because
 * Nuxt 3's `extends` mechanism is designed for Nuxt layers (directories containing
 * their own nuxt.config.ts, app.vue, pages/, etc.), not for importing individual
 * config files directly.
 *
 * When pointing `extends` to a .ts file, Nuxt shows:
 *   "WARN Cannot extend config from ./nuxt.config.base.ts"
 *
 * By using a standard ES module import and defu merge, we achieve the same result reliably.
 */
import { defineNuxtConfig } from 'nuxt/config'
import defu from 'defu'
import baseConfig from './nuxt.config.base.ts'

export default defineNuxtConfig(
  defu(
    {
      // Test-specific configuration
      modules: ['@nuxt/test-utils/module', '@nuxt/eslint'],
    },
    baseConfig
  )
)
