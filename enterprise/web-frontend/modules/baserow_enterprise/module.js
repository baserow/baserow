import path from 'path'
import {
  defineNuxtModule,
  addPlugin,
  createResolver,
  extendPages,
} from 'nuxt/kit'
import { routes, rootChildRoutes } from './routes'
import { locales } from '../../../../web-frontend/config/locales.js'
import _ from 'lodash'

export default defineNuxtModule({
  meta: {
    name: 'enterprise',
  },
  setup(options, nuxt) {
    const { resolve } = createResolver(import.meta.url)

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

      // Add login pages as children of login-pages (inherit login layout)
      const loginPagesRoute = pages.find(
        (route) => route.name === 'login-pages'
      )
      if (loginPagesRoute) {
        routes.forEach((route) => {
          if (
            !loginPagesRoute.children.find(({ name }) => name === route.name)
          ) {
            loginPagesRoute.children.push(route)
          }
        })
      }
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

    addPlugin({
      src: resolve('./plugin.js'),
    })

    // Runtime config defaults - values can be overridden at runtime via NUXT_ prefixed env vars
    // See env-remap.mjs for the env var remapping that enables backwards compatibility
    nuxt.options.runtimeConfig.public = _.defaultsDeep(
      nuxt.options.runtimeConfig.public,
      {
        baserowEnterpriseAssistantLlmModel: '',
      }
    )

    // Override Baserow's existing default.scss in favor of our own because that one
    // imports the original. We do this so that we can use the existing variables,
    // mixins, placeholders etc.
    nuxt.options.css[0] = path.resolve(__dirname, 'assets/scss/default.scss')
  },
})
