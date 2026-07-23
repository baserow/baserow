export default defineNuxtRouteMiddleware(async () => {
  const { $registry } = useNuxtApp()
  await $registry.loadDomain('database')
})
