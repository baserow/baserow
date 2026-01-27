import { defineNuxtModule, addPlugin, createResolver } from 'nuxt/kit'
import { locales } from '../../config/locales.js'

export default defineNuxtModule({
  meta: {
    name: 'integrations-module',
  },

  setup(options, nuxt) {
    const { resolve } = createResolver(import.meta.url)

    // Register main plugin
    addPlugin({
      src: resolve('./plugin.js'),
    })

    nuxt.hook('i18n:registerModule', (register) => {
      register({
        langDir: resolve('./locales'),
        locales,
      })
    })
  },
})
