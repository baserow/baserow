<template>
  <div class="filter-table-setup">
    <h3 class="text-filter-widget-settings__title margin-bottom-1">
      {{
        widget.filter_table_id
          ? $t('textFilterWidget.whatItFilters')
          : $t('filterTableSetup.question')
      }}
    </h3>
    <p class="filter-table-setup__help">
      {{ $t('filterTableSetup.questionHelp') }}
    </p>
    <p v-if="!tables.length" class="filter-table-setup__help">
      {{ $t('filterTableSetup.noTables') }}
    </p>
    <FormGroup
      v-else
      small-label
      :label="$t('filterTableSetup.table')"
      required
    >
      <Dropdown
        :model-value="widget.filter_table_id"
        show-search
        :loading="saving"
        :disabled="saving"
        :placeholder="$t('filterTableSetup.chooseTable')"
        @update:model-value="selectTable"
      >
        <DropdownItem
          v-for="table in tables"
          :key="table.id"
          :name="table.name"
          :value="table.id"
          :description="tableDescription(table)"
        />
      </Dropdown>
    </FormGroup>
  </div>
</template>

<script setup>
const props = defineProps({
  widget: { type: Object, required: true },
  dashboard: { type: Object, required: true },
  storePrefix: { type: String, default: '' },
  /** Saves widget values, resolving to whether the server accepted them. */
  save: { type: Function, required: true },
})
const { $store, $registry, $i18n } = useNuxtApp()

const saving = ref(false)

const getter = (name) =>
  $store.getters[`${props.storePrefix}dashboardApplication/${name}`]

/** How many display widgets of the dashboard show each table. */
const widgetCounts = computed(() => {
  const counts = {}
  for (const widget of getter('getWidgets')) {
    const type = $registry.get('dashboardWidget', widget.type)
    if (!type.isDisplayWidget) continue
    const tableId = getter('getDataSourceById')(
      type.getDataSourceId(widget)
    )?.table_id
    if (tableId) counts[tableId] = (counts[tableId] || 0) + 1
  }
  return counts
})

const tables = computed(() => {
  const databases = (
    $store.getters['application/getAllOfWorkspace']?.(
      props.dashboard.workspace
    ) || []
  ).filter((application) => application.type === 'database')
  const all = databases.flatMap((database) =>
    (database.tables || []).map((table) => ({
      id: table.id,
      name: table.name,
      databaseName: database.name,
    }))
  )
  // Tables the dashboard already shows come first, the busiest first.
  const count = (table) => widgetCounts.value[table.id] || 0
  return all.sort((a, b) => count(b) - count(a))
})
const tableDescription = (table) => {
  const count = widgetCounts.value[table.id] || 0
  return count
    ? $i18n.t('filterTableSetup.usedByWidgets', { count }, count)
    : table.databaseName
}

async function selectTable(id) {
  if (saving.value || id === props.widget.filter_table_id) return
  // The first table also filters the widgets added to it later, like the
  // editor will likely want: it can be turned off below.
  const values = props.widget.filter_table_id
    ? { filter_table_id: id }
    : { filter_table_id: id, apply_to_new_widgets: true }
  saving.value = true
  try {
    await props.save(values)
  } finally {
    saving.value = false
  }
}
</script>
