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
    name: '@baserow/agent',
    configKey: 'agent',
  },
  setup(options, nuxt) {
    const { resolve } = createResolver(import.meta.url)

    addPlugin(resolve('./plugin.js'))
    addPlugin(resolve('./plugins/realtime.js'))

    addRouteMiddleware({
      name: 'selectAgentApplication',
      path: resolve('./middleware/selectAgentApplication.js'),
    })

    extendPages((pages) => {
      pages.push(...routes)
    })

    nuxt.hook('i18n:registerModule', (register) => {
      register({
        langDir: resolve('./locales'),
        locales: locales.filter(({ code }) => code === 'en'),
      })
    })
  },
})
