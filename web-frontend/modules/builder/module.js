import {
  defineNuxtModule,
  addPlugin,
  createResolver,
  extendPages,
  addTemplate,
} from 'nuxt/kit'
import { routes } from './routes'
import { readFileSync } from 'node:fs'

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
  dependsOn: ['core'],
  async setup(options, nuxt) {
    const { resolve } = createResolver(import.meta.url)

    // Add main plugin
    addPlugin(resolve('./plugin.js'))

    // Add global plugin
    addPlugin(resolve('./plugins/global.js'))

    // Add routes
    extendPages((pages) => {
      pages.push(...routes)
    })

    // Create a "fake" template with the existing Nuxt router file that can be used by the
    // `plugins/router.js` above.
    const template = addTemplate({
      filename: 'custom-router.js',
      getContents: () => readFileSync(resolve('./router.js'), 'utf-8'),
    })

    nuxt.options.alias['#app/router'] = template.dst

    // Register i18n translations
    nuxt.hook('i18n:registerModule', (register) => {
      register({
        langDir: resolve('./locales'),
        locales,
      })
    })
  },
})
