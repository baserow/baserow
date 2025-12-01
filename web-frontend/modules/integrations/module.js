import path from 'path'

import en from './locales/en.json'
import fr from './locales/fr.json'
import nl from './locales/nl.json'
import de from './locales/de.json'
import it from './locales/it.json'
import es from './locales/es.json'
import pl from './locales/pl.json'
import ko from './locales/ko.json'

export default function IntegrationModule(options) {
  // Add the plugin to register the builder application.
  this.appendPlugin({
    src: path.resolve(__dirname, 'plugin.js'),
  })

  let alreadyExtended = false
  this.nuxt.hook('i18n:extend-messages', function (additionalMessages) {
    if (alreadyExtended) return
    additionalMessages.push({ en, fr, nl, de, es, it, pl, ko })
    alreadyExtended = true
  })
}
