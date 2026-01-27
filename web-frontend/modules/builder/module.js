import {
  defineNuxtModule,
  addPlugin,
  createResolver,
  extendPages,
  addTemplate,
  addRouteMiddleware,
} from 'nuxt/kit'
import { routes } from './routes'
import { locales } from '../../config/locales.js'

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
    addPlugin(resolve('./plugins/router.js'))
    addPlugin(resolve('./plugins/realtime.js'))

    addRouteMiddleware({
      name: 'selectWorkspaceBuilderPage',
      path: resolve('./middleware/selectWorkspaceBuilderPage.js'),
    })

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

    nuxt.hook('vite:extendConfig', (config) => {
      config.server ||= {}
      config.server.allowedHosts = true
    })
  },
})
