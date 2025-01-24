import en from '@baserow/modules/integrations/locales/en.json'
import fr from '@baserow/modules/integrations/locales/fr.json'
import nl from '@baserow/modules/integrations/locales/nl.json'
import de from '@baserow/modules/integrations/locales/de.json'
import es from '@baserow/modules/integrations/locales/es.json'
import it from '@baserow/modules/integrations/locales/it.json'
import pl from '@baserow/modules/integrations/locales/pl.json'
import ko from '@baserow/modules/integrations/locales/ko.json'

import { LocalBaserowIntegrationType } from '@baserow/modules/integrations/integrationTypes'
import {
  LocalBaserowGetRowServiceType,
  LocalBaserowListRowsServiceType,
  LocalBaserowAggregateRowsServiceType,
} from '@baserow/modules/integrations/serviceTypes'

export default (context) => {
  const { app, isDev } = context

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

  app.$registry.register(
    'integration',
    new LocalBaserowIntegrationType(context)
  )

  app.$registry.register('service', new LocalBaserowGetRowServiceType(context))
  app.$registry.register(
    'service',
    new LocalBaserowListRowsServiceType(context)
  )
  app.$registry.register(
    'service',
    new LocalBaserowAggregateRowsServiceType(context)
  )
}
