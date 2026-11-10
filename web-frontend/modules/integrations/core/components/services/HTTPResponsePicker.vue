<template>
  <div class="http-response-picker" role="tree">
    <div
      v-for="row in rows"
      :key="row.id"
      class="http-response-picker__row"
      :class="{
        'http-response-picker__row--selectable': row.selectable,
        'http-response-picker__row--selected': row.selected,
      }"
      :style="{ paddingLeft: `${8 + row.depth * 16}px` }"
      role="treeitem"
      tabindex="0"
      :aria-level="row.depth + 1"
      :aria-expanded="row.expandable ? row.open : undefined"
      :aria-selected="row.selected"
      @click="onRowClick(row)"
      @keydown.enter.prevent="onRowClick(row)"
      @keydown.space.prevent="onRowClick(row)"
      @keydown.right.prevent="setOpen(row, true)"
      @keydown.left.prevent="setOpen(row, false)"
    >
      <button
        v-if="row.expandable"
        type="button"
        class="http-response-picker__toggle"
        tabindex="-1"
        :aria-label="
          row.open
            ? $t('httpResponsePicker.collapse')
            : $t('httpResponsePicker.expand')
        "
        @click.stop="toggle(row)"
      >
        <i
          :class="
            row.open ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right'
          "
        />
      </button>
      <span v-else class="http-response-picker__toggle" />
      <span class="http-response-picker__key">{{ row.label }}</span>
      <span class="http-response-picker__value">{{ row.preview }}</span>
      <span
        v-if="row.selectable"
        class="http-response-picker__tag"
        :class="{ 'http-response-picker__tag--selected': row.selected }"
      >
        <i v-if="row.selected" class="iconoir-check" />
        {{
          row.isList
            ? $t('httpResponsePicker.aList')
            : $t('httpResponsePicker.oneRecord')
        }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

/**
 * Shows a response as a tree, to choose where its records are: the whole
 * response for one record, or one of the lists in it.
 */
const props = defineProps({
  response: {
    type: [Object, Array, String, Number, Boolean],
    required: false,
    default: null,
  },
  returnsList: {
    type: Boolean,
    required: false,
    default: false,
  },
  listPath: {
    type: String,
    required: false,
    default: '',
  },
})

const emit = defineEmits(['select'])

const { t } = useI18n()

const isObject = (value) =>
  value !== null && typeof value === 'object' && !Array.isArray(value)

const rowId = (segments) => JSON.stringify(segments.map((key) => `${key}`))

// A list path has dots between keys, so a key with a dot, or an empty one,
// can't be part of it.
const canBeInPath = (segments) =>
  segments.every((segment) => {
    const key = `${segment}`
    return key !== '' && !key.includes('.')
  })

const children = (value) => {
  if (Array.isArray(value)) {
    return value.map((item, index) => [index, item])
  }
  return isObject(value) ? Object.entries(value) : []
}

const preview = (value) => {
  if (Array.isArray(value)) {
    return '[…]'
  }
  if (isObject(value)) {
    return '{…}'
  }
  return JSON.stringify(value)
}

/**
 * The list which is opened in the tree while the response is read as one
 * record, to show it can be chosen: the response itself when it is a list, or
 * else the only list in it outside other lists.
 */
const onlyListSegments = computed(() => {
  if (Array.isArray(props.response)) {
    return []
  }
  const lists = []
  const findLists = (value, segments) => {
    children(value).forEach(([key, item]) => {
      if (Array.isArray(item)) {
        lists.push([...segments, key])
      } else {
        findLists(item, [...segments, key])
      }
    })
  }
  findLists(props.response, [])
  return lists.length === 1 && canBeInPath(lists[0]) ? lists[0] : null
})

const selectedSegments = computed(() => {
  if (!props.returnsList) {
    // The response is the record, unless it is a list.
    return Array.isArray(props.response) ? null : []
  }
  const path = props.listPath.trim()
  return path ? path.split('.') : []
})

// The rows a row is under, which are open for it to be shown.
const ancestorIds = (segments) =>
  segments.map((_, index) => rowId(segments.slice(0, index)))

const initialOpenIds = () =>
  new Set([
    rowId([]),
    ...ancestorIds(selectedSegments.value || []),
    ...ancestorIds(onlyListSegments.value || []),
  ])

const openIds = ref(initialOpenIds())

watch(
  () => props.response,
  () => {
    openIds.value = initialOpenIds()
  }
)

const rows = computed(() => {
  const result = []
  const selectedId = selectedSegments.value
    ? rowId(selectedSegments.value)
    : null

  const addRows = (value, segments, label) => {
    const id = rowId(segments)
    const isList = Array.isArray(value)
    const isRoot = segments.length === 0
    const open = openIds.value.has(id)
    const items = children(value)
    result.push({
      id,
      segments,
      label,
      depth: segments.length,
      preview: preview(value),
      isList,
      expandable: items.length > 0 && !isRoot,
      open,
      selectable: isRoot || (isList && canBeInPath(segments)),
      // The records of a list data source are only the list at its path.
      selected: id === selectedId && (!props.returnsList || isList),
    })
    if (open) {
      items.forEach(([key, item]) =>
        addRows(item, [...segments, key], `${key}`)
      )
    }
  }

  addRows(props.response, [], t('httpResponsePicker.response'))
  return result
})

const setOpen = (row, open) => {
  if (!row.expandable || row.open === open) {
    return
  }
  const openRows = new Set(openIds.value)
  if (open) {
    openRows.add(row.id)
  } else {
    openRows.delete(row.id)
  }
  openIds.value = openRows
}

const toggle = (row) => setOpen(row, !row.open)

const onRowClick = (row) => {
  if (row.selectable) {
    if (!row.selected) {
      emit('select', {
        returnsList: row.isList,
        listPath: row.isList ? row.segments.join('.') : '',
      })
    }
  } else if (row.expandable) {
    toggle(row)
  }
}
</script>
