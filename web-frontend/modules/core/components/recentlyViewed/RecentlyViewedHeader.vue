<template>
  <div class="recently-viewed__header">
    <h2 class="recently-viewed__title">{{ title }}</h2>

    <Dropdown
      v-if="showWorkspaceFilter"
      class="recently-viewed__filter"
      :model-value="workspaceIds"
      multiple
      fixed-items
      @update:model-value="$emit('update:workspaceIds', $event)"
    >
      <template #selectedValue>
        <span class="dropdown__selected-text">{{ workspaceLabel }}</span>
      </template>
      <template #defaultValue>
        <span class="dropdown__selected-text">{{ workspaceLabel }}</span>
      </template>
      <DropdownItem
        v-for="workspace in workspaces"
        :key="workspace.id"
        :name="workspace.name"
        :value="workspace.id"
      ></DropdownItem>
    </Dropdown>

    <Dropdown
      class="recently-viewed__filter"
      :model-value="types"
      :show-search="false"
      multiple
      fixed-items
      @update:model-value="$emit('update:types', $event)"
    >
      <template #selectedValue>
        <span class="dropdown__selected-text">{{ typeLabel }}</span>
      </template>
      <template #defaultValue>
        <span class="dropdown__selected-text">{{ typeLabel }}</span>
      </template>
      <DropdownItem
        v-for="option in typeOptions"
        :key="option.value"
        :name="option.name"
        :value="option.value"
        :icon="option.iconClass"
      ></DropdownItem>
    </Dropdown>

    <div class="recently-viewed__header-divider"></div>

    <SegmentControl
      icons-only
      size="small"
      :segments="viewModeSegments"
      :active-index="viewMode === VIEW_MODE_CARDS ? 1 : 0"
      @update:active-index="
        $emit(
          'update:viewMode',
          $event === 1 ? VIEW_MODE_CARDS : VIEW_MODE_TABLE
        )
      "
    ></SegmentControl>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#app'

import SegmentControl from '@baserow/modules/core/components/SegmentControl'

// Stored as user preferences, so the values must stay in sync with the
// `*_recently_viewed_view_mode` preference types of the backend.
const VIEW_MODE_TABLE = 'table'
const VIEW_MODE_CARDS = 'cards'

const props = defineProps({
  title: {
    type: String,
    required: true,
  },
  showWorkspaceFilter: {
    type: Boolean,
    required: false,
    default: false,
  },
  workspaceIds: {
    type: Array,
    required: true,
  },
  types: {
    type: Array,
    required: true,
  },
  viewMode: {
    type: String,
    required: true,
  },
})

defineEmits(['update:workspaceIds', 'update:types', 'update:viewMode'])

const store = useStore()
const { $registry, $i18n } = useNuxtApp()

const workspaces = computed(() => store.getters['workspace/getAllSorted'])

const workspaceLabel = computed(() =>
  props.workspaceIds.length === 0
    ? $i18n.t('recentlyViewed.allWorkspaces')
    : $i18n.t('recentlyViewed.workspacesSelected', {
        count: props.workspaceIds.length,
      })
)

const typeOptions = computed(() =>
  $registry
    .getOrderedList('lastViewedItem')
    .flatMap((itemType) => itemType.getFilterOptions())
)

const typeLabel = computed(() =>
  props.types.length === 0
    ? $i18n.t('recentlyViewed.allItems')
    : $i18n.t('recentlyViewed.itemTypesSelected', { count: props.types.length })
)

const viewModeSegments = computed(() => [
  { icon: 'iconoir-list', label: $i18n.t('recentlyViewed.tableView') },
  { icon: 'iconoir-view-grid', label: $i18n.t('recentlyViewed.cardsView') },
])
</script>
