import en from '@baserow/modules/integrations/locales/en.json'
import fr from '@baserow/modules/integrations/locales/fr.json'
import nl from '@baserow/modules/integrations/locales/nl.json'
import de from '@baserow/modules/integrations/locales/de.json'
import es from '@baserow/modules/integrations/locales/es.json'
import it from '@baserow/modules/integrations/locales/it.json'
import pl from '@baserow/modules/integrations/locales/pl.json'
import ko from '@baserow/modules/integrations/locales/ko.json'

import { LocalBaserowIntegrationType } from '@baserow/modules/integrations/localBaserow/integrationTypes'
import { SMTPIntegrationType } from '@baserow/modules/integrations/core/integrationTypes'
import { AIIntegrationType } from '@baserow/modules/integrations/ai/integrationTypes'
import {
  LocalBaserowGetRowServiceType,
  LocalBaserowListRowsServiceType,
  LocalBaserowAggregateRowsServiceType,
  LocalBaserowCreateRowWorkflowServiceType,
  LocalBaserowDeleteRowWorkflowServiceType,
  LocalBaserowUpdateRowWorkflowServiceType,
  LocalBaserowRowsCreatedTriggerServiceType,
  LocalBaserowRowsUpdatedTriggerServiceType,
  LocalBaserowRowsDeletedTriggerServiceType,
} from '@baserow/modules/integrations/localBaserow/serviceTypes'
import {
  CoreHTTPRequestServiceType,
  PeriodicTriggerServiceType,
  CoreRouterServiceType,
  CoreSMTPEmailServiceType,
  CoreHTTPTriggerServiceType,
  CoreIteratorServiceType,
} from '@baserow/modules/integrations/core/serviceTypes'
import { AIAgentServiceType } from '@baserow/modules/integrations/ai/serviceTypes'
import { SlackWriteMessageServiceType } from '@baserow/modules/integrations/slack/serviceTypes'
import { SlackBotIntegrationType } from '@baserow/modules/integrations/slack/integrationTypes'

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
  app.$registry.register('integration', new SMTPIntegrationType(context))
  app.$registry.register('integration', new AIIntegrationType(context))
  app.$registry.register('integration', new SlackBotIntegrationType(context))

  app.$registry.register('service', new LocalBaserowGetRowServiceType(context))
  app.$registry.register(
    'service',
    new LocalBaserowListRowsServiceType(context)
  )
  app.$registry.register(
    'service',
    new LocalBaserowAggregateRowsServiceType(context)
  )
  app.$registry.register(
    'service',
    new LocalBaserowCreateRowWorkflowServiceType(context)
  )
  app.$registry.register(
    'service',
    new LocalBaserowUpdateRowWorkflowServiceType(context)
  )
  app.$registry.register(
    'service',
    new LocalBaserowDeleteRowWorkflowServiceType(context)
  )
  app.$registry.register('service', new CoreHTTPRequestServiceType(context))
  app.$registry.register('service', new CoreSMTPEmailServiceType(context))
  app.$registry.register('service', new CoreRouterServiceType(context))
  app.$registry.register('service', new CoreHTTPTriggerServiceType(context))
  app.$registry.register('service', new CoreIteratorServiceType(context))
  app.$registry.register('service', new AIAgentServiceType(context))
  app.$registry.register('service', new PeriodicTriggerServiceType(context))
  app.$registry.register('service', new SlackWriteMessageServiceType(context))
  app.$registry.register(
    'service',
    new LocalBaserowRowsCreatedTriggerServiceType(context)
  )
  app.$registry.register(
    'service',
    new LocalBaserowRowsUpdatedTriggerServiceType(context)
  )
  app.$registry.register(
    'service',
    new LocalBaserowRowsDeletedTriggerServiceType(context)
  )
}
