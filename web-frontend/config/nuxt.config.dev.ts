import { defineNuxtConfig } from 'nuxt/config'
import baseConfig from './nuxt.config.base.ts'

export default defineNuxtConfig({
  ...baseConfig,
  modules: [
    ...(baseConfig.modules || []),
    ['@nuxt/eslint', { config: { typescript: false } }],
  ],
  devtools: { enabled: true },
})
