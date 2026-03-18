import { defineNuxtConfig } from 'nuxt/config'
import baseConfig from './nuxt.config.base.ts'

export default defineNuxtConfig({
  ...baseConfig,
  modules: [...(baseConfig.modules || []), '@nuxt/eslint'],
  devtools: { enabled: true },
})
