// import path from 'path'

// import { routes } from './routes'
// import en from './locales/en.json'
// import nl from './locales/nl.json'
// import fr from './locales/fr.json'
// import de from './locales/de.json'
// import es from './locales/es.json'
// import it from './locales/it.json'
// import pl from './locales/pl.json'
// import ko from './locales/ko.json'

// export default function DashboardModule(options) {
//   this.addPlugin({ src: path.resolve(__dirname, 'middleware.js') })

//   // Add the plugin to register the dashboard application.
//   this.appendPlugin({
//     src: path.resolve(__dirname, 'plugin.js'),
//   })

//   // Add all the related routes.
//   this.extendRoutes((configRoutes) => {
//     configRoutes.push(...routes)
//   })

//   let alreadyExtended = false
//   this.nuxt.hook('i18n:extend-messages', function (additionalMessages) {
//     if (alreadyExtended) return
//     additionalMessages.push({ en, fr, nl, de, es, it, pl, ko })
//     alreadyExtended = true
//   })
// }

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
    name: '@baserow/dashboard',
    configKey: 'dashboard',
    compatibility: {
      nuxt: '^3.0.0',
    },
  },
  async setup(options, nuxt) {
    const { resolve } = createResolver(import.meta.url)

    addPlugin(resolve('./plugin.js'))
    addPlugin(resolve('./plugins/realtime.js'))

    addRouteMiddleware({
      name: 'dashboardLoading',
      path: resolve('./middleware/dashboardLoading.js'),
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
