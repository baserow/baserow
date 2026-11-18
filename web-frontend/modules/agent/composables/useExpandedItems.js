import { computed, nextTick, reactive, ref, watch } from 'vue'

/** Local disclosure state; collapsing never unmounts a form or discards its draft. */
export function useExpandedItems(items, retainedItems = items) {
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
  watch(
    () => new Set(retainedItems.value.map(({ id }) => id)),
    (ids) => {
      for (const id of expandedIds) if (!ids.has(id)) expandedIds.delete(id)
    }
  )
  return { expandedIds, allExpanded, toggle, toggleAll }
}

/** Expand and scroll to a newly created configuration card once its form exists. */
export function useAgentCardList(items, createItem, retainedItems = items) {
  const disclosure = useExpandedItems(items, retainedItems)
  const list = ref(null)
  const creating = ref(false)
  async function addItem(type) {
    if (creating.value) return
    creating.value = true
    try {
      const item = await createItem(type)
      if (!item) return
      disclosure.expandedIds.add(item.id)
      await nextTick()
      list.value
        ?.querySelector(`[data-card-id="${item.id}"]`)
        ?.scrollIntoView?.({ block: 'start' })
    } finally {
      creating.value = false
    }
  }

  return { ...disclosure, list, creating, addItem }
}
