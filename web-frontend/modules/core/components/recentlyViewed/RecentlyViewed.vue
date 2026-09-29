<template>
  <div class="recently-viewed">
    <RecentlyViewedHeader
      v-model:workspace-ids="selectedWorkspaceIds"
      v-model:types="selectedTypes"
      v-model:view-mode="viewMode"
      :title="title"
      :show-workspace-filter="workspace === null"
    ></RecentlyViewedHeader>

    <RecentlyViewedSkeleton
      v-if="loading"
      :view-mode="viewMode"
      :show-workspace="workspace === null"
      :count="skeletonCount"
    ></RecentlyViewedSkeleton>

    <template v-else-if="presentedItems.length > 0 || hasMore">
      <RecentlyViewedTable
        v-if="viewMode !== 'cards'"
        :items="presentedItems"
        :show-workspace="workspace === null"
        @open="open"
      ></RecentlyViewedTable>
      <div v-else class="recently-viewed__grid">
        <RecentlyViewedCard
          v-for="item in presentedItems"
          :key="item.key"
          :item="item"
          @click="open(item)"
        ></RecentlyViewedCard>
      </div>

      <div v-if="hasMore" class="recently-viewed__footer">
        <Button
          type="secondary"
          tag="a"
          :loading="loadingMore"
          @click="loadMore()"
          >{{ $t('recentlyViewed.loadMore') }}</Button
        >
      </div>
    </template>

    <div v-else-if="filtersActive" class="recently-viewed__empty">
      <div class="recently-viewed__empty-title">
        {{ $t('recentlyViewed.noFilterMatchesTitle') }}
      </div>
      <div class="recently-viewed__empty-description">
        {{ $t('recentlyViewed.noFilterMatchesDescription') }}
      </div>
      <Button
        class="recently-viewed__empty-action"
        type="secondary"
        tag="a"
        @click="clearFilters()"
        >{{ $t('recentlyViewed.clearFilters') }}</Button
      >
    </div>

    <div v-else class="recently-viewed__empty">
      <div class="recently-viewed__empty-title">
        {{ $t('recentlyViewed.emptyTitle') }}
      </div>
      <div class="recently-viewed__empty-description">
        {{ $t('recentlyViewed.emptyDescription') }}
      </div>
      <div class="recently-viewed__empty-action">
        <slot name="empty-action"></slot>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter, useNuxtApp } from '#app'

import RecentlyViewedHeader from '@baserow/modules/core/components/recentlyViewed/RecentlyViewedHeader'
import RecentlyViewedTable from '@baserow/modules/core/components/recentlyViewed/RecentlyViewedTable'
import RecentlyViewedCard from '@baserow/modules/core/components/recentlyViewed/RecentlyViewedCard'
import RecentlyViewedSkeleton from '@baserow/modules/core/components/recentlyViewed/RecentlyViewedSkeleton'
import { useRecentlyViewedItems } from '@baserow/modules/core/composables/useRecentlyViewedItems'
import { useUserPreference } from '@baserow/modules/core/composables/useUserPreference'
import { getHumanAgoLabel } from '@baserow/modules/core/utils/date'
import { pageFinished } from '@baserow/modules/core/utils/routing'

const props = defineProps({
  // `null` lists across every workspace of the user and adds the workspace
  // filter and column.
  workspace: {
    type: Object,
    required: false,
    default: null,
  },
  title: {
    type: String,
    required: true,
  },
  viewModePreferenceKey: {
    type: String,
    required: true,
  },
})

const router = useRouter()
const nuxtApp = useNuxtApp()
const { $registry, $i18n } = nuxtApp

const selectedWorkspaceIds = ref([])
const selectedTypes = ref([])
const workspaceIds = computed(() =>
  props.workspace === null ? selectedWorkspaceIds.value : [props.workspace.id]
)
const filtersActive = computed(
  () => selectedWorkspaceIds.value.length > 0 || selectedTypes.value.length > 0
)

const viewMode = useUserPreference(props.viewModePreferenceKey, 'table')

const { items, hasMore, loading, loadingMore, fetchedAt, loadMore } =
  await useRecentlyViewedItems({
    key: `recently-viewed-${props.workspace?.id ?? 'all'}`,
    workspaceIds,
    types: selectedTypes,
  })

// Set while navigating to an item, so its icon shows a spinner like the
// application cards do.
const openingKey = ref(null)

function keyOf(entry) {
  return `${entry.type}-${entry.item.id}`
}

/**
 * Everything the row and card components need, resolved once per entry so they
 * stay presentational and the registry is consulted once per render.
 */
function presentEntry(entry) {
  const itemType = $registry.get('lastViewedItem', entry.type)
  const key = keyOf(entry)
  return {
    key,
    entry,
    name: entry.item.name,
    route: itemType.getRoute(entry),
    typeName: itemType.getName(entry),
    iconClass: itemType.getIconClass(entry),
    iconColor: itemType.getIconColor(entry),
    parentPath: itemType.getParentPath(entry),
    lastViewedLabel: getHumanAgoLabel(
      $i18n.t,
      entry.last_viewed,
      fetchedAt.value
    ),
    workspaceName: entry.workspace.name,
    workspaceInitial: entry.workspace.name.trim().charAt(0).toUpperCase(),
    loading: openingKey.value === key,
  }
}

const presentedItems = computed(() => items.value.map(presentEntry))

// Matches what the list held before, so a reload doesn't make the page jump,
// with a sensible amount for a first visit.
const skeletonCount = computed(() =>
  items.value.length ? Math.min(items.value.length, 8) : 5
)

function clearFilters() {
  selectedWorkspaceIds.value = []
  selectedTypes.value = []
}

async function open(item) {
  if (openingKey.value !== null) {
    return
  }
  openingKey.value = item.key
  try {
    await router.push(item.route)
    await pageFinished(nuxtApp)
  } finally {
    openingKey.value = null
  }
}
</script>
