import { computed, watch } from 'vue'
import { useAsyncData, showError } from '#app'

const LOADING_STATUSES = ['idle', 'pending']

/**
 * `useAsyncData` for a page that renders a skeleton loading state instead of
 * making the navigation wait for its data.
 *
 * The fetch neither blocks the navigation nor runs during server side rendering,
 * because waiting for it in either place delays the first paint of a page that
 * can already show its skeleton. That moves two things out of the page's setup:
 * an error now arrives after the page has rendered, so it's shown from a watcher
 * instead of being thrown, and the `idle` status (the tick before the fetch
 * starts) counts as loading because the previous page's data can still be in the
 * store then.
 *
 * Pages must still `await` the returned object. It isn't a promise, but an async
 * setup is what makes Suspense hydrate teleported children (contexts, modals) in
 * the order the server rendered them.
 */
export function usePageAsyncData(key, handler, options = {}) {
  const { data, status, error, refresh, execute, clear } = useAsyncData(
    key,
    handler,
    { lazy: true, server: false, ...options }
  )

  const loading = computed(() => LOADING_STATUSES.includes(status.value))

  watch(
    error,
    (value) => {
      if (value) {
        showError(value)
      }
    },
    { immediate: true }
  )

  return { data, status, error, loading, refresh, execute, clear }
}
