import { computed, reactive, watch } from 'vue'

/** Local disclosure state; collapsing never unmounts a form or discards its draft. */
export function useExpandedItems(items) {
  const expandedIds = reactive(new Set())
  const allExpanded = computed(
    () =>
      items.value.length > 0 &&
      items.value.every(({ id }) => expandedIds.has(id))
  )
  function toggle(id) {
    if (expandedIds.has(id)) expandedIds.delete(id)
    else expandedIds.add(id)
  }
  function toggleAll() {
    if (allExpanded.value) expandedIds.clear()
    else items.value.forEach(({ id }) => expandedIds.add(id))
  }
  watch(items, (values) => {
    const ids = new Set(values.map(({ id }) => id))
    for (const id of expandedIds) if (!ids.has(id)) expandedIds.delete(id)
  })
  return { expandedIds, allExpanded, toggle, toggleAll }
}
