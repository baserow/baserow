import { EnterpriseRuntimePlugin } from '@baserow_enterprise/pluginsRuntime'
import {
  RolePermissionManagerType,
  WriteFieldValuesPermissionManagerType,
} from '@baserow_enterprise/permissionManagerTypes'
import { LocalBaserowUserSourceType } from '@baserow_enterprise/integrations/userSourceTypes'
import {
  LocalBaserowPasswordAppAuthProviderType,
  OpenIdConnectAppAuthProviderType,
  SamlAppAuthProviderType,
} from '@baserow_enterprise/integrations/appAuthProviderTypes'
import {
  AuthFormElementType,
  FileInputElementType,
  GraphElementType,
} from '@baserow_enterprise/builder/elementTypes'
import {
  EnterpriseAdminRoleType,
  EnterpriseBuilderRoleType,
  EnterpriseCommenterRoleType,
  EnterpriseEditorRoleType,
  EnterpriseMemberRoleType,
  EnterpriseViewerRoleType,
  NoAccessRoleType,
  NoRoleLowPriorityRoleType,
} from '@baserow_enterprise/roleTypes'
import {
  CoreCodeServiceType,
  CoreXLSFileReaderServiceType,
} from '@baserow_enterprise/integrations/core/serviceTypes'
import {
  CoreCodeWorkflowActionType,
  CoreXLSFileReaderWorkflowActionType,
} from '@baserow_enterprise/builder/workflowActionTypes'

/** Register this entry before rendering or hydrating its routes. */
export default async function register(nuxtApp) {
  const { $config, $registry, $store, $featureFlagIsEnabled } = nuxtApp
  const context = { app: nuxtApp }
  $registry.register('plugin', new EnterpriseRuntimePlugin(context))
  $registry.register(
    'permissionManager',
    new RolePermissionManagerType(context)
  )
  $registry.register(
    'permissionManager',
    new WriteFieldValuesPermissionManagerType(context)
  )
  $registry.register('userSource', new LocalBaserowUserSourceType(context))
  $registry.register('service', new CoreXLSFileReaderServiceType(context))
  $registry.register(
    'workflowAction',
    new CoreXLSFileReaderWorkflowActionType(context)
  )
  $registry.registerNamespace('semanticSearchFieldType')
  $registry.register(
    'appAuthProvider',
    new LocalBaserowPasswordAppAuthProviderType(context)
  )
  $registry.register('appAuthProvider', new SamlAppAuthProviderType(context))
  $registry.register(
    'appAuthProvider',
    new OpenIdConnectAppAuthProviderType(context)
  )
  $registry.register('roles', new EnterpriseAdminRoleType(context))
  $registry.register('roles', new EnterpriseMemberRoleType(context))
  $registry.register('roles', new EnterpriseBuilderRoleType(context))
  $registry.register('roles', new EnterpriseEditorRoleType(context))
  $registry.register('roles', new EnterpriseCommenterRoleType(context))
  $registry.register('roles', new EnterpriseViewerRoleType(context))
  $registry.register('roles', new NoAccessRoleType(context))
  $registry.register('roles', new NoRoleLowPriorityRoleType(context))
  $registry.register('element', new AuthFormElementType(context))
  $registry.register('element', new FileInputElementType(context))
  $registry.register('element', new GraphElementType(context))
  if ($config.public.baserowEnterpriseCodeRunnerDefaultType) {
    $registry.register('service', new CoreCodeServiceType(context))
    $registry.register(
      'workflowAction',
      new CoreCodeWorkflowActionType(context)
    )
  }
}
