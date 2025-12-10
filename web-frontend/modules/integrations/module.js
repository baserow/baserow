import { defineNuxtModule, addPlugin, createResolver } from 'nuxt/kit'

const locales = [
  { code: 'en', name: 'English', file: 'en.json' },
  { code: 'fr', name: 'Français', file: 'fr.json' },
  { code: 'nl', name: 'Nederlands', file: 'nl.json' },
  { code: 'de', name: 'Deutsch', file: 'de.json' },
  { code: 'es', name: 'Español', file: 'es.json' },
  { code: 'it', name: 'Italiano', file: 'it.json' },
  { code: 'pl', name: 'Polski (Beta)', file: 'pl.json' },
  { code: 'ko', name: '한국어', file: 'ko.json' },
]

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
