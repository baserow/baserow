import {
  defineNuxtModule,
  addPlugin,
  createResolver,
  extendPages,
  addTemplate,
} from 'nuxt/kit'
import { routes } from './routes'

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
    name: '@baserow/builder',
    configKey: 'builder',
    compatibility: {
      nuxt: '^3.0.0',
    },
  },
  async setup(options, nuxt) {
    const { resolve } = createResolver(import.meta.url)

    // Add main plugin
    addPlugin(resolve('./plugin.js'))

    // Add router plugin
    addPlugin({
      src: resolve('./plugins/router.js'),
      mode: 'client',
    })

    // Add global plugin
    addPlugin(resolve('./plugins/global.js'))

    // Add routes
    extendPages((pages) => {
      pages.push(...routes)
    })

    // Register i18n translations
    nuxt.hook('i18n:registerModule', (register) => {
      register({
        langDir: resolve('./locales'),
        locales,
      })
    })
  },
})
