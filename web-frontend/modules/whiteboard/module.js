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
    name: '@baserow/whiteboard',
    configKey: 'whiteboard',
    compatibility: {
      nuxt: '^3.0.0',
    },
  },
  async setup(options, nuxt) {
    const { resolve } = createResolver(import.meta.url)

    addPlugin(resolve('./plugin.js'))
    addPlugin(resolve('./plugins/realtime.js'))

    addRouteMiddleware({
      name: 'whiteboardLoading',
      path: resolve('./middleware/whiteboardLoading.js'),
      global: false,
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
