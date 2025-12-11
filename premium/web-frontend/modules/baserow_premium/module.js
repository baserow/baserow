import {
  defineNuxtModule,
  addPlugin,
  createResolver,
  extendPages,
} from 'nuxt/kit'
import { routes } from './routes'

/*import en from './locales/en.json'
import fr from './locales/fr.json'
import nl from './locales/nl.json'
import de from './locales/de.json'
import es from './locales/es.json'
import it from './locales/it.json'
import pl from './locales/pl.json'
import ko from './locales/ko.json'*/

const locales = [
  { code: 'en', name: 'English', file: 'en.json' },
  { code: 'fr', name: 'Français', file: 'fr.json' },
  { code: 'nl', name: 'Nederlands', file: 'nl.json' },
  { code: 'de', name: 'Deutsch', file: 'de.json' },
  { code: 'es', name: 'Español', file: 'es.json' },
  { code: 'it', name: 'Italiano', file: 'it.json' },
  { code: 'pl', name: 'Polski (Beta)', file: 'pl.json' },
]

export default defineNuxtModule({
  meta: {
    name: 'premium',
  },

  setup(options, nuxt) {
    const { resolve } = createResolver(import.meta.url)

    // Register new alias to the web-frontend directory.
    nuxt.options.alias['@baserow_premium'] = resolve('./')

    /*let alreadyExtended = false
    this.nuxt.hook('i18n:extend-messages', function (additionalMessages) {
      if (alreadyExtended) return
      additionalMessages.push({ en, fr, nl, de, es, it, pl, ko })
      alreadyExtended = true
    })*/

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

    Object.assign(nuxt.options.runtimeConfig.public, {
      baserowPremiumGroupedAggregateServiceMaxSeries:
        process.env.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_SERIES || 3,
      baserowPricingUrl: process.env.BASEROW_PRICING_URL || null,
    })

    /*if (this.options.publicRuntimeConfig) {
      this.options.publicRuntimeConfig.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_SERIES =
        process.env.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_SERIES || 3
      // This environment variable exist for the SaaS to override the pricing URL, so
      // that the user can be redirected to the correct URL.
      this.options.publicRuntimeConfig.BASEROW_PRICING_URL =
        process.env.BASEROW_PRICING_URL || null
    }*/
  },
})
