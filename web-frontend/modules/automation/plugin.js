import en from '@baserow/modules/automation/locales/en.json'
import fr from '@baserow/modules/automation/locales/fr.json'
import nl from '@baserow/modules/automation/locales/nl.json'
import de from '@baserow/modules/automation/locales/de.json'
import es from '@baserow/modules/automation/locales/es.json'
import it from '@baserow/modules/automation/locales/it.json'
import pl from '@baserow/modules/automation/locales/pl.json'
import ko from '@baserow/modules/automation/locales/ko.json'

import { registerRealtimeEvents } from '@baserow/modules/automation/realtime'
import { AutomationApplicationType } from '@baserow/modules/automation/applicationTypes'
import automationApplicationStore from '@baserow/modules/automation/store/automationApplication'
import { FF_AUTOMATION } from '@baserow/modules/core/plugins/featureFlags'

export default (context) => {
  const { app, isDev, store } = context

  // Allow locale file hot reloading in dev
  if (isDev && app.i18n) {
    const { i18n } = app
    i18n.mergeLocaleMessage('en', en)
    i18n.mergeLocaleMessage('fr', fr)
    i18n.mergeLocaleMessage('nl', nl)
    i18n.mergeLocaleMessage('de', de)
    i18n.mergeLocaleMessage('es', es)
    i18n.mergeLocaleMessage('it', it)
    i18n.mergeLocaleMessage('pl', pl)
    i18n.mergeLocaleMessage('ko', ko)
  }

  registerRealtimeEvents(app.$realtime)

  store.registerModule('automationApplication', automationApplicationStore)
  store.registerModule(
    'template/automationApplication',
    automationApplicationStore
  )

  if (app.$featureFlagIsEnabled(FF_AUTOMATION)) {
    app.$registry.register(
      'application',
      new AutomationApplicationType(context)
    )
  }
}
