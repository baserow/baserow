<template>
  <LocalBaserowTableServiceConditionalForm
    :model-value="localGroup.filters"
    :filter-groups="localGroup.filter_groups"
    :filter-type="localGroup.filter_type"
    :fields="fields"
    :read-only="readOnly"
    @update:model-value="update('filters', $event)"
    @update:filter-groups="update('filter_groups', $event)"
    @update:filter-type="update('filter_type', $event)"
  />
</template>

<script setup>
import LocalBaserowTableServiceConditionalForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableServiceConditionalForm'
import DashboardFormulaInput from '@baserow/modules/dashboard/components/DashboardFormulaInput'

const props = defineProps({
  group: { type: Object, required: true },
  fields: { type: Array, required: true },
  dashboard: { type: Object, required: true },
  owner: { type: Object, default: null },
  readOnly: { type: Boolean, default: false },
})
const emit = defineEmits(['update'])
const storePrefix = inject('storePrefix', ref(''))
const localGroup = ref(props.group)
watch(
  () => props.group,
  (group) => {
    localGroup.value = group
  },
  { deep: true }
)
provide('formulaComponent', DashboardFormulaInput)
provide(
  'dataProvidersAllowed',
  computed(() => (props.owner ? ['widget_data'] : []))
)
provide(
  'dashboardFormulaContext',
  computed(() => ({
    dashboard: props.dashboard,
    storePrefix: storePrefix.value,
    owningWidgetId: props.owner?.id,
  }))
)
let updatePending = false
/** Save related condition/group changes together before the server remaps group IDs. */
const update = (key, value) => {
  if (props.readOnly) return
  localGroup.value = { ...localGroup.value, [key]: value }
  if (updatePending) return
  updatePending = true
  nextTick(() => {
    updatePending = false
    emit('update', localGroup.value)
  })
}
</script>
