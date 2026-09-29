import {
  defineNuxtModule,
  addPlugin,
  createResolver,
  addRouteMiddleware,
  extendPages,
} from 'nuxt/kit'
import { rootChildRoutes, routes } from './routes'
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
      name: 'selectWorkspaceDatabaseTable',
      path: resolve('./middleware/selectWorkspaceDatabaseTable'),
    })

    extendPages((pages) => {
      pages.push(...routes)

      const rootRoute = pages.find((route) => route.name === 'root')
      rootChildRoutes.forEach((route) => {
        if (!rootRoute.children.find(({ name }) => name === route.name)) {
          rootRoute.children.push(route)
        }
      })
    })

    nuxt.hook('i18n:registerModule', (register) => {
      register({
        langDir: resolve('./locales'),
        locales,
      })
    })

    // Database specific styles. Added as its own entry rather than replacing
    // core's, so it lands after whichever default.scss premium or enterprise
    // has put in first place.
    nuxt.options.css.push(resolve('./assets/scss/default.scss'))
  },
})
