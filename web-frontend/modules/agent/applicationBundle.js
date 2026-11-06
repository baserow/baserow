import registerApplication from '@baserow/modules/agent/pluginApplication'
import registerRealtime from '@baserow/modules/agent/plugins/realtimeApplication'

/** Initialize this application's registries, stores and realtime handlers together. */
export default async function register(app) {
  await registerApplication(app)
  if (app.$realtime) await registerRealtime(app)
}

export { default as AgentApplicationContext } from '@baserow/modules/agent/components/AgentApplicationContext'
export { default as AgentApplicationForm } from '@baserow/modules/agent/components/AgentApplicationForm'
export { default as AgentApplicationSidebar } from '@baserow/modules/agent/components/AgentApplicationSidebar'
