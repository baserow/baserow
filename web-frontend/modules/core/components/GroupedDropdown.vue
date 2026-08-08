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
      <GroupedMenu
        ref="menu"
        :items="items"
        :model-value="currentValue"
        :search-placeholder="searchPlaceholder"
        :empty-text="emptyText"
        :show-search="showSearch"
        @select="selectItem"
        @disabled-click="emit('disabled-click', $event)"
        @close="hide"
      >
        <template #item-meta="{ item }">
          <slot name="item-meta" :item="item" />
        </template>
      </GroupedMenu>
    </Context>
  </div>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'

import Context from '@baserow/modules/core/components/Context'
import GroupedMenu from '@baserow/modules/core/components/GroupedMenu'

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
  panelHeight: {
    type: String,
    required: false,
    default: null,
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
const menu = ref(null)
const open = ref(false)
const menuMinWidth = ref(0)

const currentValue = computed(() =>
  props.modelValue !== undefined ? props.modelValue : props.value
)
const selectedResult = computed(() =>
  findSelectedItem(props.items, currentValue.value)
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
    result.group?.image ||
    null
  )
})
const selectedIcon = computed(() => {
  const result = selectedResult.value
  if (!result) {
    return null
  }
  return (
    result.item.selectedIcon || result.item.icon || result.group?.icon || null
  )
})
const contextStyle = computed(() => ({
  minWidth: menuMinWidth.value ? `${menuMinWidth.value}px` : undefined,
  '--grouped-menu-panel-height': props.panelHeight,
}))

function isGroup(item) {
  return Array.isArray(item?.children)
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
  menu.value?.reset()
}

async function focusMenu() {
  await nextTick()
  menu.value?.focus()
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

function selectItem(item) {
  emit('input', item.value)
  emit('update:modelValue', item.value)
  emit('change', item.value)
  emit('select', item)
  hide()
}

defineExpose({ hide, show, toggle })
</script>
