import {
  CoreCodeNodeType,
  CoreXLSFileReaderNodeType,
} from '@baserow_enterprise/automation/nodeTypes'

export default function registerEnterpriseAutomationDomain(nuxtApp) {
  const { $config, $registry } = nuxtApp
  const context = { app: nuxtApp }

  if ($config.public.baserowEnterpriseCodeRunnerDefaultType) {
    $registry.register('node', new CoreCodeNodeType(context))
  }
  $registry.register('node', new CoreXLSFileReaderNodeType(context))
}
