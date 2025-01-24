import path from 'path'

import { routes } from './routes'

import en from './locales/en.json'
import fr from './locales/fr.json'
import nl from './locales/nl.json'
import de from './locales/de.json'
import es from './locales/es.json'
import it from './locales/it.json'
import pl from './locales/pl.json'
import ko from './locales/ko.json'

export default function () {
  this.nuxt.hook('i18n:extend-messages', (additionalMessages) => {
    additionalMessages.push({ en, fr, nl, de, es, it, pl, ko })
  })

  // Register new alias to the web-frontend directory.
  this.options.alias['@baserow_enterprise'] = path.resolve(__dirname, './')

  // Remove the existing index route and add our own routes.
  this.extendRoutes((configRoutes) => {
    const settingsRoute = configRoutes.find(
      (route) => route.name === 'settings'
    )

    // Prevent for adding the route multiple times
    if (!settingsRoute.children.find(({ path }) => path === 'teams')) {
      settingsRoute.children.push({
        name: 'settings-teams',
        path: 'teams',
        component: path.resolve(__dirname, 'pages/settings/teams.vue'),
      })
    }

    configRoutes.push(...routes)
  })

  this.appendPlugin({
    src: path.resolve(__dirname, 'plugin.js'),
  })

  // Override Baserow's existing default.scss in favor of our own because that one
  // imports the original. We do this so that we can use the existing variables,
  // mixins, placeholders etc.
  this.options.css[0] = path.resolve(__dirname, 'assets/scss/default.scss')
}
