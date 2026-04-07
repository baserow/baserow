/**
 * A promise that resolves when the new page is fully loaded. Should be used directly
 * after changing the route. Use like:
 *
 * await router.push({ name: 'login', query: { noredirect: null } })
 * await pageFinished(nuxtApp)
 * await nextTick()
 * // executed when the page is fully loaded
 */
export const pageFinished = async (nuxtApp) => {
  return new Promise((resolve) => {
    nuxtApp.hooks.hookOnce('page:finish', resolve)
  })
}
