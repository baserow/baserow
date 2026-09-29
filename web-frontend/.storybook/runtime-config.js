import { runtimeConfig } from 'virtual:nuxt-runtime-config'

// Nuxt's fetch module reads the app config during import, before the framework's
// per-story setup initializes the Nuxt app. Seed it before those imports run.
window.__NUXT__ = {
  ...window.__NUXT__,
  config: runtimeConfig,
}
