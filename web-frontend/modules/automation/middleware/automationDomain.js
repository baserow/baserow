export default defineNuxtRouteMiddleware(async () => {
  const { $registry } = useNuxtApp()
  await Promise.all([
    $registry.loadDomain('database'),
    $registry.loadDomain('automation'),
  ])
})
