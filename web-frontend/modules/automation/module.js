import {
  defineNuxtModule,
  addPlugin,
  createResolver,
  extendPages,
  addRouteMiddleware,
} from 'nuxt/kit'
import { routes } from './routes'
import { locales } from '../../config/locales.js'

export default defineNuxtModule({
  meta: {
    name: 'automation-module',
  },
  dependsOn: ['core', 'database'],
  setup(options, nuxt) {
    const { resolve } = createResolver(import.meta.url)

    // Register main plugin
    addPlugin({
      src: resolve('./plugin.js'),
    })

    addPlugin({
      src: resolve('./plugins/realtime.js'),
    })

    addRouteMiddleware({
      name: 'selectWorkspaceAutomationWorkflow',
      path: resolve('./middleware/selectWorkspaceAutomationWorkflow.js'),
    })

    extendPages((pages) => {
      pages.push(...routes)
    })

    nuxt.hook('i18n:registerModule', (register) => {
      register({
        langDir: resolve('./locales'),
        locales,
      })
    })
  },
})
