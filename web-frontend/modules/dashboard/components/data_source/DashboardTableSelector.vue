<template>
  <Dropdown
    :model-value="modelValue"
    show-search
    fixed-items
    :error="error"
    @update:model-value="selectTable"
  >
    <DropdownSection
      v-for="database in databases"
      :key="database.id"
      :title="`${database.name} (${database.id})`"
    >
      <DropdownItem
        v-for="table in database.tables"
        :key="table.id"
        :name="table.name"
        :value="table.id"
        indented
        >{{ table.name }}</DropdownItem
      >
    </DropdownSection>
  </Dropdown>
  <Modal ref="confirmation" small @hidden="pendingTableId = null">
    <h2 class="box__title">{{ $t('dashboardTableSelector.confirmTitle') }}</h2>
    <p>{{ $t('dashboardTableSelector.confirmMessage') }}</p>
    <div class="actions actions--right actions--gap margin-bottom-0">
      <Button type="secondary" @click="confirmation.hide()">{{
        $t('action.cancel')
      }}</Button>
      <Button @click="confirmChange">{{
        $t('dashboardTableSelector.confirmAction')
      }}</Button>
    </div>
  </Modal>
</template>

<script setup>
const props = defineProps({
  modelValue: { type: Number, default: null },
  databases: { type: Array, required: true },
  dataSource: { type: Object, required: true },
  storePrefix: { type: String, default: '' },
  error: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
const { $store, $registry } = useNuxtApp()
const confirmation = ref(null)
const pendingTableId = ref(null)
const hasConditions = computed(() => {
  if (props.dataSource.filters?.length) return true
  const widgets =
    $store.getters[`${props.storePrefix}dashboardApplication/getWidgets`]
  const targetIds = new Set(
    widgets
      .filter((widget) => {
        const type = $registry.get('dashboardWidget', widget.type)
        return (
          type.isDisplayWidget &&
          type.getDataSourceId(widget) === props.dataSource.id
        )
      })
      .map(({ id }) => id)
  )
  // Disabled links and the unused empty-value branch are reset too.
  return widgets.some(
    (widget) =>
      $registry.get('dashboardWidget', widget.type).isFilterWidget &&
      widget.target_filters?.some(
        (link) =>
          targetIds.has(link.target_widget_id) &&
          (link.group?.filters?.length ||
            link.alternative_group?.filters?.length)
      )
  )
})
function selectTable(tableId) {
  if (tableId === props.modelValue) return
  if (hasConditions.value) {
    pendingTableId.value = tableId
    confirmation.value.show()
  } else emit('update:modelValue', tableId)
}
function confirmChange() {
  const tableId = pendingTableId.value
  confirmation.value.hide()
  if (tableId !== null) emit('update:modelValue', tableId)
}
watch(
  () => [props.dataSource.id, props.modelValue],
  () => confirmation.value?.hide()
)
</script>
