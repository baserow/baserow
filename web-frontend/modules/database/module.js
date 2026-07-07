import {
  defineNuxtModule,
  addPlugin,
  createResolver,
  addRouteMiddleware,
  extendPages,
} from 'nuxt/kit'
import { routes } from './routes'
import { locales } from '../../config/locales.js'

export default defineNuxtModule({
  meta: {
    name: 'database',
  },

  setup(options, nuxt) {
    const { resolve } = createResolver(import.meta.url)

    // Register main plugin
    addPlugin({
      src: resolve('./plugin.js'),
    })
    addPlugin({
      src: resolve('./plugin/store.js'),
    })
    addPlugin({
      src: resolve('./plugin/realtime.js'),
    })

    addRouteMiddleware({
      name: 'tableLoading',
      path: resolve('./middleware/tableLoading'),
    })

    addRouteMiddleware({
      name: 'selectWorkspaceDatabaseTable',
      path: resolve('./middleware/selectWorkspaceDatabaseTable'),
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
