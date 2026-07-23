import {
  AuthFormElementType,
  FileInputElementType,
} from '@baserow_enterprise/builder/elementTypes'
import { MadeWithBaserowBuilderPageDecoratorType } from '@baserow_enterprise/builderPageDecoratorTypes'
import { CustomCodeBuilderSettingType } from '@baserow_enterprise/builderSettingTypes'
import {
  CoreCodeWorkflowActionType,
  CoreXLSFileReaderWorkflowActionType,
} from '@baserow_enterprise/builder/workflowActionTypes'

export default function registerEnterpriseBuilderDomain(nuxtApp) {
  const { $config, $registry } = nuxtApp
  const context = { app: nuxtApp }

  $registry.register('element', new AuthFormElementType(context))
  $registry.register('element', new FileInputElementType(context))

  $registry.register(
    'builderPageDecorator',
    new MadeWithBaserowBuilderPageDecoratorType(context)
  )

  $registry.register(
    'builderSettings',
    new CustomCodeBuilderSettingType(context)
  )

  if ($config.public.baserowEnterpriseCodeRunnerDefaultType) {
    $registry.register(
      'workflowAction',
      new CoreCodeWorkflowActionType(context)
    )
  }
  $registry.register(
    'workflowAction',
    new CoreXLSFileReaderWorkflowActionType(context)
  )
}
