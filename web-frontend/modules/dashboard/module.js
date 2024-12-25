import path from 'path'

import { routes } from './routes'
import en from './locales/en.json'
import nl from './locales/nl.json'
import fr from './locales/fr.json'
import de from './locales/de.json'
import es from './locales/es.json'
import it from './locales/it.json'
import pl from './locales/pl.json'
import ko from './locales/ko.json'

export default function DashboardModule(options) {
  this.addPlugin({ src: path.resolve(__dirname, 'middleware.js') })

  // Add the plugin to register the dashboard application.
  this.appendPlugin({
    src: path.resolve(__dirname, 'plugin.js'),
  })

  // Add all the related routes.
  this.extendRoutes((configRoutes) => {
    configRoutes.push(...routes)
  })

  this.nuxt.hook('i18n:extend-messages', function (additionalMessages) {
    additionalMessages.push({ en })
    additionalMessages.push({ nl })
    additionalMessages.push({ fr })
    additionalMessages.push({ de })
    additionalMessages.push({ es })
    additionalMessages.push({ it })
    additionalMessages.push({ pl })
    additionalMessages.push({ ko })
  })
}
