import path from 'path'
import {
  defineNuxtModule,
  addPlugin,
  createResolver,
  extendPages,
} from 'nuxt/kit'
import { routes, rootChildRoutes } from './routes'

import en from './locales/en.json'
import fr from './locales/fr.json'
import nl from './locales/nl.json'
import de from './locales/de.json'
import es from './locales/es.json'
import it from './locales/it.json'
import pl from './locales/pl.json'
import ko from './locales/ko.json'

const locales = [
  { code: 'en', name: 'English', file: 'en.json' },
  { code: 'fr', name: 'Français', file: 'fr.json' },
  { code: 'nl', name: 'Nederlands', file: 'nl.json' },
  { code: 'de', name: 'Deutsch', file: 'de.json' },
  { code: 'es', name: 'Español', file: 'es.json' },
  { code: 'it', name: 'Italiano', file: 'it.json' },
  { code: 'pl', name: 'Polski (Beta)', file: 'pl.json' },
]

export default defineNuxtModule({
  meta: {
    name: 'enterprise',
  },
  setup(options, nuxt) {
    const { resolve } = createResolver(import.meta.url)
    /*let alreadyExtended = false
    this.nuxt.hook('i18n:extend-messages', function (additionalMessages) {
      if (alreadyExtended) return
      additionalMessages.push({ en, fr, nl, de, es, it, pl, ko })
      alreadyExtended = true
    })*/

    // Register new alias to the web-frontend directory.
    nuxt.options.alias['@baserow_enterprise'] = path.resolve(__dirname, './')

    extendPages((pages) => {
      const rootRoute = pages.find((route) => route.name === 'root')
      const settingsRoute = rootRoute.children.find(
        (route) => route.name === 'settings'
      )

      // TODO MIG do we still need that?
      // Prevent for adding the route multiple times
      if (!settingsRoute.children.find(({ path }) => path === 'teams')) {
        settingsRoute.children.push({
          name: 'settings-teams',
          path: 'teams',
          file: path.resolve(__dirname, 'pages/settings/teams.vue'),
        })
      }

      // Add enterprise routes as children of root (inherit layout and middlewares)
      rootChildRoutes.forEach((route) => {
        if (!rootRoute.children.find(({ name }) => name === route.name)) {
          rootRoute.children.push(route)
        }
      })

      // Add top-level routes (login pages, etc.)
      pages.push(...routes)
    })

    nuxt.hook('i18n:registerModule', (register) => {
      register({
        langDir: resolve('./locales'),
        locales,
      })
    })

    addPlugin({
      src: resolve('./plugin.js'),
    })

    addPlugin({
      src: resolve('./plugins/realtime.js'),
    })

    // Remove the existing index route and add our own routes.
    /*this.extendRoutes((configRoutes) => {
      const settingsRoute = configRoutes.find(
        (route) => route.name === 'settings'
      )

      // Prevent for adding the route multiple times
      if (!settingsRoute.children.find(({ path }) => path === 'teams')) {
        settingsRoute.children.push({
          name: 'settings-teams',
          path: 'teams',
          component: path.resolve(__dirname, 'pages/settings/teams.vue'),
        })
      }

      configRoutes.push(...routes)
    })*/

    addPlugin({
      src: resolve('./plugin.js'),
    })

    Object.assign(nuxt.options.runtimeConfig.public, {
      baserowEnterpriseAssistantLLMModel:
        process.env.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL || null,
    })

    // Override Baserow's existing default.scss in favor of our own because that one
    // imports the original. We do this so that we can use the existing variables,
    // mixins, placeholders etc.
    nuxt.options.css[0] = path.resolve(__dirname, 'assets/scss/default.scss')

    /*if (this.options.publicRuntimeConfig) {
      this.options.publicRuntimeConfig.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL =
        process.env.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL || null
    }*/
  },
})
