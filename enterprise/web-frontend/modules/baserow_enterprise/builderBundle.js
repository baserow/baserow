import { MadeWithBaserowBuilderPageDecoratorType } from '@baserow_enterprise/builderPageDecoratorTypes'
import { CustomCodeBuilderSettingType } from '@baserow_enterprise/builderSettingTypes'

/** Register this feature only when its application is used. */
export default async function register(nuxtApp) {
  const { $registry } = nuxtApp
  const context = { app: nuxtApp }
  $registry.register(
    'builderPageDecorator',
    new MadeWithBaserowBuilderPageDecoratorType(context)
  )
  $registry.register(
    'builderSettings',
    new CustomCodeBuilderSettingType(context)
  )
}
