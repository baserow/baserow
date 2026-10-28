import { registerChatRunRealtimeEvents } from '@baserow/modules/core/chatRuns/realtime'

export default defineNuxtPlugin({
  name: 'chat-runs',
  dependsOn: ['realtime', 'store'],
  setup(nuxtApp) {
    const store = nuxtApp.$store
    registerChatRunRealtimeEvents(nuxtApp.$realtime)
    if (import.meta.client) {
      const resume = () => {
        if (store.getters['auth/isAuthenticated']) {
          store.dispatch('chatRuns/resumeFollowers')
        }
      }
      window.addEventListener('focus', resume)
      window.addEventListener('online', resume)
      store.watch(
        (_, getters) => getters['auth/isAuthenticated'],
        (authenticated) => {
          if (!authenticated) store.dispatch('chatRuns/disconnect')
        }
      )
    }
  },
})
