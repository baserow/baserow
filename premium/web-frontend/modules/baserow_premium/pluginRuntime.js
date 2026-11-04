import {
  SingleSelectFormattingType,
  MultipleSelectFormattingType,
} from '@baserow_premium/dashboard/chartFieldFormatting'
import { LocalBaserowGroupedAggregateRowsServiceType } from '@baserow_premium/integrations/localBaserow/serviceTypes'
import { PremiumLicenseType } from '@baserow_premium/licenseTypes'

/** Register this entry before rendering or hydrating its routes. */
export default async function register(nuxtApp) {
  const { $registry, $store, $clientErrorMap, $i18n } = nuxtApp
  const context = { app: nuxtApp }
  $registry.registerNamespace('aiFieldOutputType')
  $registry.registerNamespace('paidFeature')
  $registry.registerNamespace('license')
  $registry.registerNamespace('groupedAggregation')
  $registry.registerNamespace('chartFieldFormatting')
  $registry.register('license', new PremiumLicenseType(context))

  $registry.register(
    'chartFieldFormatting',
    new SingleSelectFormattingType(context)
  )
  $registry.register(
    'chartFieldFormatting',
    new MultipleSelectFormattingType(context)
  )
  $registry.register(
    'service',
    new LocalBaserowGroupedAggregateRowsServiceType(context)
  )
  $registry.registerNamespace('timelineFieldRules')
}
