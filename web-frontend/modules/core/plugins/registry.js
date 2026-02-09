import { defineNuxtPlugin } from '#app'
import { Registry } from '@baserow/modules/core/registry'

export default defineNuxtPlugin({
  name: 'registry',
  setup(nuxtApp) {
    const registry = new Registry()
    nuxtApp.provide('registry', registry)
  },
})
