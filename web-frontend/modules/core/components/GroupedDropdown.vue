<template>
  <div
    class="dropdown grouped-dropdown"
    :class="{
      'dropdown--disabled': disabled,
      'dropdown--large': size === 'large',
      'dropdown--error': error,
    }"
  >
    <button
      ref="trigger"
      type="button"
      class="dropdown__selected grouped-dropdown__trigger"
      :disabled="disabled"
      aria-haspopup="menu"
      :aria-expanded="open ? 'true' : 'false'"
      @click="toggle"
    >
      <template v-if="selectedResult">
        <img
          v-if="selectedImage"
          class="dropdown__selected-image"
          :src="selectedImage"
          :alt="selectedLabel"
        />
        <i
          v-else-if="selectedIcon"
          class="dropdown__selected-icon"
          :class="selectedIcon"
        />
        <span class="dropdown__selected-text" :title="selectedLabel">
          {{ selectedLabel }}
        </span>
      </template>
      <span v-else class="dropdown__selected-placeholder">
        {{ placeholder }}
      </span>
      <i class="dropdown__toggle-icon iconoir-nav-arrow-down" />
    </button>

    <Context
      ref="context"
      class="grouped-dropdown__context"
      max-height-if-outside-viewport
      :style="contextStyle"
      @shown="onShown"
      @hidden="onHidden"
    >
      <div
        class="grouped-dropdown__menu"
        :class="{
          'grouped-dropdown__menu--grouped': hasGroupedItems,
        }"
      >
        <MenuSearch
          v-if="showSearch"
          ref="menuSearch"
          v-model="query"
          :placeholder="searchPlaceholder"
          @keydown="handleSearchKeydown"
        />

        <div v-if="visibleItems.length" class="grouped-dropdown__panels">
          <div
            v-if="navigationMenuItems.length"
            class="grouped-dropdown__navigation"
          >
            <MenuList
              ref="navigationMenu"
              :items="navigationMenuItems"
              :model-value="activeNavigationValue"
              :empty-text="emptyText"
              :show-descriptions="false"
              @select="selectNavigationItem"
              @disabled-click="emit('disabled-click', $event)"
              @close="hide"
              @navigate-right="navigateToActions"
            />
          </div>

          <div
            class="grouped-dropdown__actions"
            :class="{
              'grouped-dropdown__actions--only': !navigationMenuItems.length,
            }"
          >
            <MenuList
              ref="actionMenu"
              :items="actionItems"
              :model-value="currentValue"
              :empty-text="emptyText"
              @select="selectItem"
              @disabled-click="emit('disabled-click', $event)"
              @close="hide"
              @navigate-left="focusNavigation"
            />
          </div>
        </div>
        <div v-else class="grouped-dropdown__empty">
          {{ emptyText }}
        </div>
      </div>
    </Context>
  </div>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'

import Context from '@baserow/modules/core/components/Context'
import MenuList from '@baserow/modules/core/components/MenuList'
import MenuSearch from '@baserow/modules/core/components/MenuSearch'

const props = defineProps({
  items: {
    type: Array,
    required: true,
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
  placeholder: {
    type: String,
    required: false,
    default: '',
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
  disabled: {
    type: Boolean,
    required: false,
    default: false,
  },
  error: {
    type: Boolean,
    required: false,
    default: false,
  },
  showSearch: {
    type: Boolean,
    required: false,
    default: true,
  },
  size: {
    type: String,
    required: false,
    validator: (value) => ['regular', 'large'].includes(value),
    default: 'regular',
  },
})

const emit = defineEmits([
  'input',
  'update:modelValue',
  'change',
  'select',
  'disabled-click',
  'show',
  'hide',
])

const context = ref(null)
const trigger = ref(null)
const menuSearch = ref(null)
const navigationMenu = ref(null)
const actionMenu = ref(null)
const open = ref(false)
const menuMinWidth = ref(0)
const query = ref('')
const activeGroupKey = ref(null)

const currentValue = computed(() =>
  props.modelValue !== undefined ? props.modelValue : props.value
)
const nonEmptyItems = computed(() => removeEmptyGroups(props.items))
const hasGroupedItems = computed(() => nonEmptyItems.value.some(hasChildren))
const visibleItems = computed(() => {
  const normalizedQuery = normalizeSearchValue(query.value)
  if (!normalizedQuery) {
    return nonEmptyItems.value
  }
  return filterGroupedItems(nonEmptyItems.value, normalizedQuery)
})
const groupedItems = computed(() =>
  visibleItems.value.filter((item) => hasChildren(item))
)
const selectableGroups = computed(() =>
  groupedItems.value.filter((item) => !item.disabled)
)
const selectedResult = computed(() =>
  findSelectedItem(nonEmptyItems.value, currentValue.value)
)
const selectedGroupKey = computed(() =>
  getItemIdentity(selectedResult.value?.ancestors[0])
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
const navigationItems = computed(() =>
  groupedItems.value.length ? visibleItems.value : []
)
const navigationMenuItems = computed(() =>
  navigationItems.value.map((item) =>
    hasChildren(item) ? { ...item, value: getItemIdentity(item) } : item
  )
)
const activeNavigationValue = computed(() => {
  if (
    selectedResult.value &&
    selectedResult.value.ancestors.length === 0 &&
    navigationItems.value.includes(selectedResult.value.item)
  ) {
    return selectedResult.value.item.value
  }
  return getItemIdentity(activeGroup.value)
})
const actionItems = computed(() =>
  activeGroup.value
    ? activeGroup.value.children
    : navigationItems.value.length
      ? []
      : visibleItems.value
)
const selectedLabel = computed(() => selectedResult.value?.item.label || '')
const selectedImage = computed(() => {
  const result = selectedResult.value
  if (!result) {
    return null
  }
  return (
    result.item.selectedImage ||
    result.item.image ||
    result.ancestors.at(-1)?.image ||
    null
  )
})
const selectedIcon = computed(() => {
  const result = selectedResult.value
  if (!result) {
    return null
  }
  return (
    result.item.selectedIcon ||
    result.item.icon ||
    result.ancestors.at(-1)?.icon ||
    null
  )
})
const contextStyle = computed(() => ({
  minWidth: menuMinWidth.value ? `${menuMinWidth.value}px` : undefined,
}))

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
  return items.reduce((filteredItems, item) => {
    if (Array.isArray(item.children)) {
      const children = removeEmptyGroups(item.children)
      if (children.length) {
        filteredItems.push({ ...item, children })
      }
    } else {
      filteredItems.push(item)
    }
    return filteredItems
  }, [])
}

function filterGroupedItems(items, normalizedQuery) {
  return items.reduce((filteredItems, item) => {
    if (hasChildren(item)) {
      const children = filterGroupedItems(item.children, normalizedQuery)
      if (children.length) {
        filteredItems.push({ ...item, children })
      }
    } else if (itemMatchesQuery(item, normalizedQuery)) {
      filteredItems.push(item)
    }
    return filteredItems
  }, [])
}

function hasChildren(item) {
  return Array.isArray(item.children) && item.children.length > 0
}

function getItemIdentity(item) {
  return item?.id ?? item?.value ?? item?.label ?? null
}

function findSelectedItem(items, value, ancestors = []) {
  for (const item of items) {
    if (hasChildren(item)) {
      const result = findSelectedItem(item.children, value, [
        ...ancestors,
        item,
      ])
      if (result) {
        return result
      }
    } else if (Object.is(item.value, value)) {
      return { item, ancestors }
    }
  }
  return null
}

async function show() {
  if (props.disabled || open.value || !trigger.value) {
    return
  }
  menuMinWidth.value = trigger.value.getBoundingClientRect().width
  await context.value.show(trigger.value, 'bottom', 'left', 4, 0)
}

function hide() {
  context.value?.hide()
}

function toggle() {
  if (open.value) {
    hide()
  } else {
    show()
  }
}

function resetMenu() {
  query.value = ''
  activeGroupKey.value = null
  navigationMenu.value?.reset()
  actionMenu.value?.reset()
}

async function focusMenu() {
  await nextTick()
  if (props.showSearch && menuSearch.value) {
    menuSearch.value.focus()
  } else if (navigationMenuItems.value.length) {
    navigationMenu.value?.focus()
  } else {
    actionMenu.value?.focus()
  }
}

async function onShown() {
  open.value = true
  resetMenu()
  await focusMenu()
  emit('show')
}

function onHidden() {
  open.value = false
  resetMenu()
  emit('hide')
}

function selectNavigationItem(item) {
  if (hasChildren(item)) {
    activeGroupKey.value = getItemIdentity(item)
    return
  }
  selectItem(item)
}

function selectItem(item) {
  emit('input', item.value)
  emit('update:modelValue', item.value)
  emit('change', item.value)
  emit('select', item)
  hide()
}

async function navigateToActions(item) {
  if (!hasChildren(item) || item.disabled) {
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
    hide()
  } else if (event.key === 'ArrowDown') {
    event.preventDefault()
    if (navigationMenuItems.value.length) {
      navigationMenu.value?.focus()
    } else {
      actionMenu.value?.focus()
    }
  }
}

defineExpose({ hide, show, toggle })
</script>
