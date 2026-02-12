import {
  defineNuxtModule,
  addPlugin,
  createResolver,
  extendPages,
} from 'nuxt/kit'
import { routes } from './routes'
import { locales } from '../../../../web-frontend/config/locales.js'
import _ from 'lodash'

export default defineNuxtModule({
  meta: {
    name: 'premium',
  },

  setup(options, nuxt) {
    const { resolve } = createResolver(import.meta.url)

    // Register new alias to the web-frontend directory.
    nuxt.options.alias['@baserow_premium'] = resolve('./')

    // Register locales
    nuxt.hook('i18n:registerModule', (register) => {
      register({
        langDir: resolve('./locales'),
        locales,
      })
    })

    extendPages((pages) => {
      pages.push(...routes)
    })

    addPlugin({
      src: resolve('./plugin.js'),
    })

    addPlugin({
      src: resolve('./plugins/license.js'),
    })

    addPlugin({
      src: resolve('./plugins/realtime.js'),
    })

    // Override Baserow's existing default.scss in favor of our own because that one
    // imports the original. We do this so that we can use the existing variables,
    // mixins, placeholders etc.
    nuxt.options.css[0] = resolve('./assets/scss/default.scss')

    // Runtime config defaults - values can be overridden at runtime via NUXT_ prefixed env vars
    // See env-remap.mjs for the env var remapping that enables backwards compatibility
    nuxt.options.runtimeConfig.public = _.defaultsDeep(
      nuxt.options.runtimeConfig.public,
      {
        baserowPremiumGroupedAggregateServiceMaxSeries: 3,
        baserowPricingUrl: '',
      }
    )
  },
})
