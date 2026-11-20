import {
  defineNuxtModule,
  addPlugin,
  createResolver,
  extendPages,
} from 'nuxt/kit'
import { routes as oauthAccountRoutes } from './oauthAccount/routes'
import { locales } from '../../config/locales.js'

export default defineNuxtModule({
  meta: {
    name: 'integrations-module',
  },

  setup(options, nuxt) {
    const { resolve } = createResolver(import.meta.url)

    // Register main plugin
    addPlugin({
      src: resolve('./plugin.js'),
    })

    extendPages((pages) => {
      pages.push(...oauthAccountRoutes)
    })

    nuxt.hook('i18n:registerModule', (register) => {
      register({
        langDir: resolve('./locales'),
        locales,
      })
    })
  },
})
