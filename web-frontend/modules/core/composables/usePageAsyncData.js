import { computed, watch, onServerPrefetch } from 'vue'
import { useAsyncData, showError } from '#app'

/**
 * Page-level wrapper around `useAsyncData` that never blocks client-side
 * navigation. The page component mounts immediately, so a skeleton can be
 * shown while the handler resolves, giving the user instant feedback when
 * navigating.
 *
 * Usage in a page `<script setup>`:
 *
 *   const { data, ready } = await usePageAsyncData('my-key', async () => { ... })
 *
 * Template pattern:
 *
 *   <MyPageSkeleton v-if="!ready" />
 *   <div v-else>...real page...</div>
 *
 * Rules:
 * - DO `await` this composable. The returned object is not a promise, so the
 *   await resolves within a microtask and doesn't block the navigation. It
 *   does make the page an async setup component, exactly like the previous
 *   blocking `await useAsyncData` pattern, which is required for Suspense to
 *   hydrate teleported children (Context, Modal) in the same order as the
 *   server rendered them. Without the await the first page load logs
 *   hydration mismatches.
 * - Gate templates on `ready`, never on `!pending`. On client-side navigation
 *   the status is `idle` for a tick before the fetch starts, so `!pending`
 *   would briefly render the real content with empty data.
 * - Keep throwing `createError({ ..., fatal: true })` inside the handler for
 *   error pages. On the server the error is re-thrown during the render so
 *   the error page is returned, exactly like the blocking `await useAsyncData`
 *   pattern. On the client the error is promoted via `showError` after the
 *   page has mounted.
 *
 * SSR behavior: the handler still runs and is awaited during server-side
 * rendering, so a first page load always responds with the fully rendered
 * page and never with a skeleton. During hydration the payload data marks the
 * state as ready immediately, so there is no skeleton flash either.
 */
export function usePageAsyncData(key, handler, options = {}) {
  const asyncData = useAsyncData(key, handler, { lazy: true, ...options })
  const { data, status, error, refresh } = asyncData

  if (import.meta.server) {
    onServerPrefetch(async () => {
      // The returned object is promise-augmented and settles when the handler
      // settles, without ever rejecting. Rejections land in the `error` ref.
      await asyncData
      if (error.value) {
        throw error.value
      }
    })
  } else {
    watch(
      error,
      (err) => {
        if (err) {
          showError(err)
        }
      },
      { immediate: true }
    )
  }

  const pending = computed(() => status.value === 'pending')
  const ready = computed(() => status.value === 'success')

  // `asyncData` is the promise-augmented useAsyncData return value. Pages that
  // must redirect based on the handler result (e.g. `data.value.redirect`) can
  // `await asyncData` inside their own `onServerPrefetch` to make the redirect
  // work server-side, combined with a client-side `watch` on `data`.
  return { data, status, pending, error, refresh, ready, asyncData }
}
