import { useNuxtApp, useRouter, useRuntimeConfig } from '#imports'

export default defineNuxtPlugin(() => {
  if (!import.meta.client) return

  const runtimeConfig = useRuntimeConfig()
  const enabled = runtimeConfig.public.baserowExtraClientScriptEnabled
  if (enabled !== true && enabled !== 'true') return

  const nuxtApp = useNuxtApp()
  const router = useRouter()

  window.__baserow = {
    $router: router,
    config: runtimeConfig.public,
    hook: (name, fn) => nuxtApp.hook(name, fn),
  }

  const el = document.createElement('script')
  el.src = '/_baserow-extra/plugin.js'
  el.async = true
  document.head.appendChild(el)
})
