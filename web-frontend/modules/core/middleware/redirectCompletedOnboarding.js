export default defineNuxtRouteMiddleware(() => {
  const { $store } = useNuxtApp()
  const user = $store.getters['auth/getUserObject']

  if (user.completed_onboarding) {
    return navigateTo({ name: 'dashboard' })
  }
})
