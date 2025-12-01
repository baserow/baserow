import path from 'path'

import { routes } from './routes'
import en from './locales/en.json'
import fr from './locales/fr.json'
import nl from './locales/nl.json'
import de from './locales/de.json'
import it from './locales/it.json'
import es from './locales/es.json'
import pl from './locales/pl.json'
import ko from './locales/ko.json'

export default function BuilderModule(options) {
  this.addPlugin({ src: path.resolve(__dirname, 'middleware.js') })

  // Add the plugin to register the builder application.
  this.appendPlugin({
    src: path.resolve(__dirname, 'plugin.js'),
  })

  // Override the existing generated Nuxt router.js file, so that we can change the
  // router by our own.
  this.addPlugin({
    src: path.resolve(__dirname, 'plugins/router.js'),
    fileName: 'router.js',
  })
  this.addPlugin({ src: path.resolve(__dirname, 'plugins/global.js') })

  // Create a "fake" template with the existing Nuxt router file that can be used by the
  // `plugins/router.js` above.
  this.addTemplate({
    fileName: 'defaultRouter.js',
    src: require.resolve('@nuxt/vue-app/template/router'),
  })

  // Add all the related routes.
  this.extendRoutes((configRoutes) => {
    configRoutes.push(...routes)
  })

  let alreadyExtended = false
  this.nuxt.hook('i18n:extend-messages', function (additionalMessages) {
    if (alreadyExtended) return
    additionalMessages.push({ en, fr, nl, de, es, it, pl, ko })
    alreadyExtended = true
  })
}
