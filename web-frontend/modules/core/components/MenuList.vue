<template>
  <div class="menu-list" @keydown="handleKeydown">
    <div v-if="searchable" class="menu-list__search">
      <i class="menu-list__search-icon iconoir-search" />
      <input
        ref="searchInput"
        v-model="query"
        class="menu-list__search-input"
        type="search"
        :placeholder="searchPlaceholder"
      />
    </div>

    <ul
      v-if="visibleItems.length"
      v-auto-overflow-scroll
      class="menu-list__items"
      role="menu"
    >
      <li
        v-for="(item, index) in visibleItems"
        :key="getItemKey(item, index)"
        class="menu-list__item"
        role="none"
      >
        <button
          :ref="setItemButton"
          v-tooltip="item.disabledReason || null"
          type="button"
          class="menu-list__item-button"
          :class="{
            'menu-list__item-button--active': isActive(item),
            'menu-list__item-button--disabled': item.disabled,
            'menu-list__item-button--with-description':
              showDescriptions && item.description,
          }"
          role="menuitem"
          :aria-disabled="item.disabled ? 'true' : undefined"
          @click="selectItem(item)"
        >
          <img
            v-if="item.image"
            class="menu-list__item-image"
            :src="item.image"
            :alt="item.label"
          />
          <i
            v-else-if="item.icon"
            class="menu-list__item-icon"
            :class="item.icon"
          />

          <span class="menu-list__item-content">
            <span class="menu-list__item-title">
              <span class="menu-list__item-label">
                {{ item.label }}
              </span>
              <slot name="item-meta" :item="item" />
            </span>
            <template v-if="showDescriptions && item.description">
              <span class="menu-list__item-description">
                {{ item.description }}
              </span>
            </template>
          </span>
        </button>
      </li>
    </ul>
    <div v-else class="menu-list__empty">
      {{ emptyText }}
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUpdate, ref, watch } from 'vue'

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
  searchable: {
    type: Boolean,
    required: false,
    default: false,
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
  showDescriptions: {
    type: Boolean,
    required: false,
    default: true,
  },
})

const emit = defineEmits([
  'select',
  'disabled-click',
  'close',
  'navigate-left',
  'navigate-right',
])

const query = ref('')
const searchInput = ref(null)
const itemButtons = ref([])

const currentValue = computed(() =>
  props.modelValue !== undefined ? props.modelValue : props.value
)
const visibleItems = computed(() => {
  const normalizedQuery = normalizeSearchValue(query.value)
  if (!normalizedQuery) {
    return props.items
  }
  return props.items.filter((item) => itemMatchesQuery(item, normalizedQuery))
})

onBeforeUpdate(() => {
  itemButtons.value = []
})

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

function getItemKey(item, index) {
  return item.id ?? item.value ?? item.label ?? index
}

function isActive(item) {
  return item.value !== undefined && Object.is(item.value, currentValue.value)
}

function setItemButton(element) {
  if (element) {
    itemButtons.value.push(element)
  }
}

function selectItem(item) {
  if (item.disabled) {
    emit('disabled-click', item)
    return
  }
  emit('select', item)
}

function focusItem(index) {
  const buttons = itemButtons.value.filter(Boolean)
  if (!buttons.length) {
    return
  }
  const boundedIndex = Math.min(Math.max(index, 0), buttons.length - 1)
  buttons[boundedIndex].focus()
}

function handleListNavigation(event) {
  const buttons = itemButtons.value.filter(Boolean)
  if (!buttons.length) {
    return
  }
  const currentIndex = buttons.indexOf(document.activeElement)
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    focusItem(currentIndex < buttons.length - 1 ? currentIndex + 1 : 0)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    focusItem(currentIndex > 0 ? currentIndex - 1 : buttons.length - 1)
  } else if (event.key === 'Home') {
    event.preventDefault()
    focusItem(0)
  } else if (event.key === 'End') {
    event.preventDefault()
    focusItem(buttons.length - 1)
  }
}

function handleKeydown(event) {
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('close')
    return
  }
  const buttons = itemButtons.value.filter(Boolean)
  if (buttons.includes(document.activeElement)) {
    const currentItem =
      visibleItems.value[buttons.indexOf(document.activeElement)]
    if (event.key === 'ArrowLeft') {
      event.preventDefault()
      emit('navigate-left', currentItem)
      return
    }
    if (event.key === 'ArrowRight') {
      event.preventDefault()
      emit('navigate-right', currentItem)
      return
    }
  }
  handleListNavigation(event)
}

function reset() {
  query.value = ''
}

async function focus() {
  await nextTick()
  if (props.searchable && searchInput.value) {
    searchInput.value.focus()
    return
  }
  const activeIndex = visibleItems.value.findIndex(isActive)
  focusItem(activeIndex >= 0 ? activeIndex : 0)
}

defineExpose({ focus, reset })
</script>
