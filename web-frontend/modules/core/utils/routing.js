/**
 * A promise that resolves when the new page is fully loaded. Should be used directly
 * after changing the route. Use like:
 *
 * await router.push({ name: 'login', query: { noredirect: null } })
 * await pageFinished()
 * await nextTick()
 * // executed when the page is fully loaded
 */
export const pageFinished = async () => {
  return new Promise((resolve) => {
    const nuxtApp = useNuxtApp()
    nuxtApp.hooks.hookOnce('page:finish', resolve)
  })
}
