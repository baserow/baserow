import { defineNuxtConfig } from 'nuxt/config'

export default defineNuxtConfig({
  extends: ['./config/nuxt.config.base.ts'],
  modules: ['@nuxt/test-utils/module'],
})
