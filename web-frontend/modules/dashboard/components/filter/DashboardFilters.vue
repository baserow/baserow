<template>
  <div v-if="filters.length" class="dashboard-filters">
    <DashboardFilterControl
      v-for="filter in filters"
      :key="filter.id"
      v-sortable="{
        id: filter.id,
        update: orderFilters,
        handle: '.control__label',
        direction: 'horizontal',
        enabled: canReorder,
      }"
      :filter="filter"
      :applied-values="applied(filter.id)"
      :option-state="options(filter.id)"
      :edit-mode="editMode"
      :selected="selected?.id === filter.id"
      :can-apply="canApply(filter)"
      :can-reorder="canReorder"
      :can-duplicate="canDuplicate"
      :can-delete="canDelete(filter)"
      :actions-disabled="reordering"
      :busy="pendingFilterIds.has(filter.id)"
      :save-values="(values) => apply(filter, values)"
      @select="dispatch('selectFilter', filter.id)"
      @duplicate="duplicate(filter)"
      @delete="remove(filter)"
      @options="
        dispatch('fetchFilterOptions', { filterId: filter.id, ...$event })
      "
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useNuxtApp } from '#app'
import DashboardFilterControl from '@baserow/modules/dashboard/components/filter/DashboardFilterControl'
import { getNextAvailableNameInSequence } from '@baserow/modules/core/utils/string'
import { notifyIf } from '@baserow/modules/core/utils/error'

const props = defineProps({
  dashboard: { type: Object, required: true },
  storePrefix: { type: String, default: '' },
})
const { $store, $hasPermission } = useNuxtApp()
const pendingFilterIds = ref(new Set())
const reordering = ref(false)
const key = computed(() => `${props.storePrefix}dashboardApplication/`)
const getter = (name) => $store.getters[key.value + name]
const dispatch = (name, values) => $store.dispatch(key.value + name, values)
const filters = computed(() => getter('getFilters'))
const editMode = computed(() => getter('isEditMode'))
const selected = computed(() => getter('getSelectedFilter'))
const applied = (id) => getter('getAppliedFilterValues')(id)
const options = (id) => getter('getFilterOptions')(id)
const canReorder = computed(
  () =>
    !reordering.value &&
    pendingFilterIds.value.size === 0 &&
    editMode.value &&
    filters.value.length > 1 &&
    $hasPermission(
      'dashboard.order_filters',
      props.dashboard,
      props.dashboard.workspace.id
    )
)
const canDuplicate = computed(() =>
  $hasPermission(
    'dashboard.create_filter',
    props.dashboard,
    props.dashboard.workspace.id
  )
)
const canDelete = (filter) =>
  $hasPermission(
    'dashboard.filter.delete',
    filter,
    props.dashboard.workspace.id
  )
const canApply = (filter) =>
  $hasPermission(
    'dashboard.filter.update',
    filter,
    props.dashboard.workspace.id
  )
async function apply(filter, values) {
  if (!canApply(filter) || pendingFilterIds.value.has(filter.id)) return false
  pendingFilterIds.value.add(filter.id)
  try {
    await dispatch('applyFilter', { filterId: filter.id, values })
    return true
  } catch (error) {
    notifyIf(error, 'dashboard')
    return false
  } finally {
    pendingFilterIds.value.delete(filter.id)
  }
}
async function orderFilters(order) {
  if (!canReorder.value) return
  reordering.value = true
  try {
    await dispatch('orderFilters', order)
  } catch (error) {
    notifyIf(error, 'dashboard')
  } finally {
    reordering.value = false
  }
}
async function duplicate(filter) {
  if (
    !editMode.value ||
    reordering.value ||
    !canDuplicate.value ||
    pendingFilterIds.value.has(filter.id)
  )
    return
  pendingFilterIds.value.add(filter.id)
  try {
    const {
      type,
      operator,
      mode,
      multiple,
      formula_value: formulaValue,
      values,
    } = filter
    const label = getNextAvailableNameInSequence(
      filter.label,
      filters.value.map(({ label }) => label),
      {
        pattern: (name, index) => {
          const suffix = ` ${index + 1}`
          return `${name.slice(0, 255 - suffix.length)}${suffix}`
        },
      }
    )
    await dispatch('createFilter', {
      label,
      type,
      operator,
      mode,
      multiple,
      formula_value: formulaValue,
      values,
    })
  } catch (error) {
    notifyIf(error, 'dashboard')
  } finally {
    pendingFilterIds.value.delete(filter.id)
  }
}
async function remove(filter) {
  if (
    !editMode.value ||
    reordering.value ||
    !canDelete(filter) ||
    pendingFilterIds.value.has(filter.id)
  )
    return
  pendingFilterIds.value.add(filter.id)
  try {
    await dispatch('deleteFilter', filter.id)
  } catch (error) {
    notifyIf(error, 'dashboard')
  } finally {
    pendingFilterIds.value.delete(filter.id)
  }
}
</script>
