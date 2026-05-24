import {
  useHead,
  useNuxtApp,
  useRequestEvent,
  useRuntimeConfig,
} from '#imports'
import EnterpriseFeatures from '@baserow_enterprise/features'

const getUrls = (raw) =>
  raw
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean)

const bootstrapScript = (config) => `
window.__baserow = window.__baserow || {};
window.__baserow.config = ${JSON.stringify(config).replace(/</g, '\\u003c')};
window.__baserow._queuedHooks = window.__baserow._queuedHooks || [];
window.__baserow.hook = function(name, fn) {
  window.__baserow._queuedHooks.push([name, fn]);
};
`

export default defineNuxtRouteMiddleware(async () => {
  if (import.meta.client) return

  const event = import.meta.server ? useRequestEvent() : null

  if (import.meta.server && !event) return

  const runtimeConfig = useRuntimeConfig()
  const raw = runtimeConfig.public.baserowExtraClientScriptUrls
  if (!raw) return

  const urls = getUrls(raw)
  if (urls.length === 0) return

  const nuxtApp = useNuxtApp()
  const store = nuxtApp.$store

  // This runs on SSR so entitled extra scripts can be emitted into the initial HTML
  // head and execute before hydration/first paint. We must gate here, per request,
  // because module-level head injection would bypass the ENTERPRISE_SETTINGS check and
  // load the scripts for every visitor.
  if (!store.getters['settings/isLoaded']) {
    await store.dispatch('settings/load')
  }

  if (!nuxtApp.$hasFeature(EnterpriseFeatures.ENTERPRISE_SETTINGS)) {
    return
  }

  useHead({
    script: [
      {
        key: 'baserow-extra-client-script-bootstrap',
        innerHTML: bootstrapScript(runtimeConfig.public),
        tagPosition: 'head',
      },
      ...urls.map((src, index) => ({
        key: `baserow-extra-client-script-${index}`,
        src,
        tagPosition: 'head',
        'data-baserow-extra-client-script': 'true',
      })),
    ],
  })
})
