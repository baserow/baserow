export default defineNuxtRouteMiddleware(async () => {
  const { $registry } = useNuxtApp()
  // Local Baserow integrations resolve database field and aggregation types,
  // including on published pages that never visit a database route.
  await Promise.all([
    $registry.loadDomain('database'),
    $registry.loadDomain('builder'),
  ])
})
