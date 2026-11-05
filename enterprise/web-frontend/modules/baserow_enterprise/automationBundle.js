import {
  CoreCodeActionNodeType,
  CoreXLSFileReaderActionNodeType,
} from '@baserow_enterprise/automation/nodeTypes'

/** Register this feature only when its application is used. */
export default async function register(nuxtApp) {
  const { $config, $registry } = nuxtApp
  const context = { app: nuxtApp }
  if ($config.public.baserowEnterpriseCodeRunnerDefaultType) {
    $registry.register('node', new CoreCodeActionNodeType(context))
  }
  $registry.register('node', new CoreXLSFileReaderActionNodeType(context))
}
