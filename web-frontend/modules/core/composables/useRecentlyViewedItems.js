import { computed, ref, toValue, watch } from 'vue'
import { useNuxtApp } from '#app'

import { usePageAsyncData } from '@baserow/modules/core/composables/usePageAsyncData'
import LastViewedService from '@baserow/modules/core/services/lastViewed'
import { notifyIf } from '@baserow/modules/core/utils/error'

// Kept small because the page is meant to answer "what was I working on", and a
// button fetches more for whoever needs it.
export const RECENTLY_VIEWED_PAGE_SIZE = 20

/**
 * Loads the recently viewed items of the current user page by page. The first
 * page goes through `usePageAsyncData`, so the page paints its skeleton instead
 * of waiting for it, and changing a filter reloads from the start.
 *
 * @param {string} key Unique per list, so two lists never share the async data.
 * @param {import('vue').MaybeRefOrGetter<number[]>} workspaceIds
 * @param {import('vue').MaybeRefOrGetter<string[]>} types Filter values as
 *   produced by `LastViewedItemType.getFilterOptions`.
 */
export async function useRecentlyViewedItems({
  key,
  workspaceIds,
  types,
  pageSize = RECENTLY_VIEWED_PAGE_SIZE,
}) {
  const { $client } = useNuxtApp()
  const service = LastViewedService($client)

  // The pages the load more button added on top of the first one.
  const nextPages = ref([])
  const loadingMore = ref(false)

  async function fetchPage(offset) {
    const { data } = await service.fetchItems({
      workspaceIds: toValue(workspaceIds),
      types: toValue(types),
      limit: pageSize,
      offset,
    })
    // The moment of the request travels with the page, so the relative dates
    // don't move while it is on screen.
    return { ...data, fetched_at: new Date().toISOString() }
  }

  const { data, loading, refresh } = await usePageAsyncData(
    key,
    () => fetchPage(0),
    { watch: [() => toValue(workspaceIds), () => toValue(types)] }
  )

  // A reloaded first page replaces everything that was loaded on top of it.
  watch(data, () => {
    nextPages.value = []
  })

  const pages = computed(() =>
    data.value ? [data.value, ...nextPages.value] : []
  )
  const items = computed(() => pages.value.flatMap((page) => page.results))
  const hasMore = computed(() => pages.value.at(-1)?.has_more ?? false)
  const fetchedAt = computed(() => data.value?.fetched_at ?? null)

  async function loadMore() {
    if (loadingMore.value || !hasMore.value) {
      return
    }
    // The first page can be replaced while this request is in flight, which
    // makes the response belong to filters that are no longer selected.
    const requestedFor = data.value
    loadingMore.value = true
    try {
      const page = await fetchPage(items.value.length)
      if (data.value === requestedFor) {
        nextPages.value = [...nextPages.value, page]
      }
    } catch (error) {
      notifyIf(error)
    } finally {
      loadingMore.value = false
    }
  }

  return { items, hasMore, loading, loadingMore, fetchedAt, refresh, loadMore }
}
