<template>
  <div
    class="grouped-menu"
    :class="{
      'grouped-menu--grouped': hasGroupedItems,
    }"
  >
    <MenuSearch
      v-if="showSearch"
      ref="menuSearch"
      v-model="query"
      :placeholder="searchPlaceholder"
      @keydown="handleSearchKeydown"
    />

    <div v-if="visibleItems.length" class="grouped-menu__panels">
      <div v-if="navigationMenuItems.length" class="grouped-menu__navigation">
        <MenuList
          ref="navigationMenu"
          class="grouped-menu__menu-list"
          :items="navigationMenuItems"
          :model-value="activeNavigationValue"
          :empty-text="emptyText"
          :show-descriptions="false"
          @select="selectNavigationItem"
          @disabled-click="emit('disabled-click', $event)"
          @close="emit('close')"
          @navigate-right="navigateToActions"
        />
      </div>

      <div
        class="grouped-menu__actions"
        :class="{
          'grouped-menu__actions--only': !navigationMenuItems.length,
        }"
      >
        <MenuList
          ref="actionMenu"
          class="grouped-menu__menu-list"
          :items="actionItems"
          :model-value="currentValue"
          :empty-text="emptyText"
          @select="selectItem"
          @disabled-click="emit('disabled-click', $event)"
          @close="emit('close')"
          @navigate-left="focusNavigation"
        >
          <template #item-meta="{ item }">
            <slot name="item-meta" :item="item" />
          </template>
        </MenuList>
      </div>
    </div>
    <div v-else class="grouped-menu__empty">
      {{ emptyText }}
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'

import MenuList from '@baserow/modules/core/components/MenuList'
import MenuSearch from '@baserow/modules/core/components/MenuSearch'

const props = defineProps({
  items: {
    type: Array,
    required: true,
    /**
     * A flat list of selectable items, or a list of groups containing direct
     * selectable items.
     */
    validator: (items) => {
      const isGroup = (item) => Array.isArray(item?.children)
      const isAction = (item) => item != null && !isGroup(item)
      const containsGroups = items.some(isGroup)

      return containsGroups
        ? items.every((item) => isGroup(item) && item.children.every(isAction))
        : items.every(isAction)
    },
  },
  modelValue: {
    validator: () => true,
    required: false,
    default: undefined,
  },
  value: {
    validator: () => true,
    required: false,
    default: undefined,
  },
  searchPlaceholder: {
    type: String,
    required: false,
    default: '',
  },
  emptyText: {
    type: String,
    required: false,
    default: '',
  },
  showSearch: {
    type: Boolean,
    required: false,
    default: true,
  },
})

const emit = defineEmits(['select', 'disabled-click', 'close'])

const menuSearch = ref(null)
const navigationMenu = ref(null)
const actionMenu = ref(null)
const query = ref('')
const activeGroupKey = ref(null)

const currentValue = computed(() =>
  props.modelValue !== undefined ? props.modelValue : props.value
)
const isGroupedInput = computed(() => props.items.some(isGroup))
const nonEmptyItems = computed(() =>
  isGroupedInput.value
    ? removeEmptyGroups(props.items)
    : props.items.filter(isAction)
)
const hasGroupedItems = computed(
  () => isGroupedInput.value && nonEmptyItems.value.length > 0
)
const visibleItems = computed(() => {
  const normalizedQuery = normalizeSearchValue(query.value)
  if (!normalizedQuery) {
    return nonEmptyItems.value
  }
  return isGroupedInput.value
    ? filterGroupedItems(nonEmptyItems.value, normalizedQuery)
    : nonEmptyItems.value.filter((item) =>
        itemMatchesQuery(item, normalizedQuery)
      )
})
const groupedItems = computed(() =>
  isGroupedInput.value ? sortGroupsByLabel(visibleItems.value) : []
)
const selectableGroups = computed(() =>
  groupedItems.value.filter((item) => !item.disabled)
)
const selectedResult = computed(() =>
  findSelectedItem(nonEmptyItems.value, currentValue.value)
)
const selectedGroupKey = computed(() =>
  getItemIdentity(selectedResult.value?.group)
)
const activeGroup = computed(
  () =>
    selectableGroups.value.find(
      (item) => getItemIdentity(item) === activeGroupKey.value
    ) ||
    selectableGroups.value.find(
      (item) => getItemIdentity(item) === selectedGroupKey.value
    ) ||
    selectableGroups.value[0] ||
    null
)
const navigationMenuItems = computed(() =>
  groupedItems.value.map((item) => ({
    ...item,
    value: getItemIdentity(item),
  }))
)
const activeNavigationValue = computed(() => getItemIdentity(activeGroup.value))
const actionItems = computed(() =>
  isGroupedInput.value ? activeGroup.value?.children || [] : visibleItems.value
)

watch(
  () => props.items,
  () => reset()
)

function normalizeSearchValue(value) {
  return String(value || '')
    .trim()
    .toLocaleLowerCase()
}

function itemMatchesQuery(item, normalizedQuery) {
  const aliases = Array.isArray(item.aliases)
    ? item.aliases
    : item.aliases
      ? [item.aliases]
      : []
  return [item.label, item.description, ...aliases].some((value) =>
    normalizeSearchValue(value).includes(normalizedQuery)
  )
}

function removeEmptyGroups(items) {
  return items
    .filter(isGroup)
    .map((group) => ({
      ...group,
      children: group.children.filter(isAction),
    }))
    .filter(({ children }) => children.length > 0)
}

function filterGroupedItems(groups, normalizedQuery) {
  return groups
    .map((group) => {
      const children = group.children.filter((item) =>
        itemMatchesQuery(item, normalizedQuery)
      )
      return children.length ? { ...group, children } : null
    })
    .filter(Boolean)
}

function sortGroupsByLabel(groups) {
  return [...groups].sort((firstGroup, secondGroup) =>
    String(firstGroup.label || '').localeCompare(
      String(secondGroup.label || ''),
      undefined,
      { sensitivity: 'base' }
    )
  )
}

function isGroup(item) {
  return Array.isArray(item?.children)
}

function isAction(item) {
  return item != null && !isGroup(item)
}

function getItemIdentity(item) {
  return item?.id ?? item?.value ?? item?.label ?? null
}

function findSelectedItem(items, value) {
  for (const item of items) {
    if (isGroup(item)) {
      const selectedItem = item.children.find((child) =>
        Object.is(child.value, value)
      )
      if (selectedItem) {
        return { item: selectedItem, group: item }
      }
    } else if (Object.is(item.value, value)) {
      return { item, group: null }
    }
  }
  return null
}

function reset() {
  query.value = ''
  activeGroupKey.value = null
  navigationMenu.value?.reset()
  actionMenu.value?.reset()
}

async function focus() {
  await nextTick()
  if (props.showSearch && menuSearch.value) {
    menuSearch.value.focus()
  } else if (navigationMenuItems.value.length) {
    navigationMenu.value?.focus()
  } else {
    actionMenu.value?.focus()
  }
}

function selectNavigationItem(item) {
  activeGroupKey.value = getItemIdentity(item)
}

function selectItem(item) {
  emit('select', item)
}

async function navigateToActions(item) {
  if (item.disabled) {
    return
  }
  activeGroupKey.value = getItemIdentity(item)
  await nextTick()
  actionMenu.value?.focus()
}

function focusNavigation() {
  navigationMenu.value?.focus()
}

function handleSearchKeydown(event) {
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('close')
  } else if (event.key === 'ArrowDown') {
    event.preventDefault()
    if (navigationMenuItems.value.length) {
      navigationMenu.value?.focus()
    } else {
      actionMenu.value?.focus()
    }
  }
}

defineExpose({ focus, reset })
</script>
