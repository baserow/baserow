import {
  defineNuxtModule,
  addPlugin,
  createResolver,
  extendPages,
  addTemplate,
  addRouteMiddleware,
  addServerHandler,
} from 'nuxt/kit'
import { routes } from './routes'
import { locales } from '../../config/locales.js'

export default defineNuxtModule({
  meta: {
    name: '@baserow/builder',
    configKey: 'builder',
  },
  dependsOn: ['core'],
  async setup(options, nuxt) {
    const { resolve } = createResolver(import.meta.url)

    nuxt.options.runtimeConfig.public ||= {}
    nuxt.options.runtimeConfig.public.builderPreviewUrl ??=
      'http://localhost:3000'

    // Add main plugin
    addPlugin(resolve('./plugin.js'))

    // Add global plugin
    addPlugin(resolve('./plugins/global.js'))
    addPlugin(resolve('./plugins/previewClientHandler.js'))
    addPlugin(resolve('./plugins/router.js'))
    addPlugin(resolve('./plugins/realtime.js'))
    addPlugin(resolve('./plugins/pendingLogin.client.js'))

    addRouteMiddleware({
      name: 'selectWorkspaceBuilderPage',
      path: resolve('./middleware/selectWorkspaceBuilderPage.js'),
    })
    addRouteMiddleware({
      name: 'exchangePreviewToken',
      path: resolve('./middleware/exchangePreviewToken.js'),
    })

    addServerHandler({
      middleware: true,
      handler: resolve('./server/middleware/authCallback.js'),
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
