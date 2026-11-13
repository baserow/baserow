<template>
  <FormRow class="margin-bottom-2">
    <FormGroup
      :label="$t('localBaserowTableSelector.tableFieldLabel')"
      :horizontal="horizontal"
      :horizontal-narrow="horizontal"
      small-label
      required
    >
      <Dropdown
        :model-value="modelValue"
        show-search
        fixed-items
        :size="dropdownSize"
        :error="error"
        @update:model-value="onTableSelect"
      >
        <DropdownSection
          v-for="database in databases"
          :key="database.id"
          :title="`${database.name} (${database.id})`"
        >
          <DropdownItem
            v-for="table in serviceType.supportedTables(database.tables)"
            :key="table.id"
            :name="table.name"
            :value="table.id"
            :description="getTableDescription(table)"
            indented
            >{{ table.name }}</DropdownItem
          >
        </DropdownSection>
      </Dropdown>
    </FormGroup>
    <FormGroup
      v-if="displayViewDropdown"
      :label="$t('localBaserowTableSelector.viewFieldLabel')"
      small-label
      required
    >
      <Dropdown
        :model-value="viewId"
        :show-search="false"
        :disabled="modelValue === null"
        fixed-items
        :size="dropdownSize"
        @update:model-value="$emit('update:view-id', $event)"
      >
        <DropdownItem
          :name="$t('localBaserowTableSelector.chooseNoView')"
          :value="null"
          >{{ $t('localBaserowTableSelector.chooseNoView') }}</DropdownItem
        >
        <DropdownItem
          v-for="view in views"
          :key="view.id"
          :name="view.name"
          :value="view.id"
        >
          {{ view.name }}
        </DropdownItem>
      </Dropdown>
    </FormGroup>
  </FormRow>
</template>

<script>
export default {
  name: 'LocalBaserowTableSelector',
  props: {
    modelValue: {
      type: Number,
      required: false,
      default: null,
    },
    horizontal: {
      type: Boolean,
      default: false,
    },
    error: {
      type: Boolean,
      default: false,
    },
    viewId: {
      type: Number,
      required: false,
      default: null,
    },
    databases: {
      type: Array,
      required: true,
    },
    serviceType: {
      type: Object,
      required: true,
    },
    displayViewDropdown: {
      type: Boolean,
      default: true,
    },
    dropdownSize: {
      type: String,
      required: false,
      validator: function (value) {
        return ['regular', 'large'].includes(value)
      },
      default: 'regular',
    },
  },
  emits: ['update:modelValue', 'update:view-id'],
  computed: {
    databaseSelected() {
      return this.databases.find((database) =>
        database.tables.some((table) => table.id === this.modelValue)
      )
    },
    views() {
      return (
        this.databaseSelected?.views.filter(
          (view) => view.table_id === this.modelValue
        ) || []
      )
    },
  },
  methods: {
    getTableDescription(table) {
      if (table.is_two_way_data_sync) {
        return this.$t(
          'localBaserowTableSelector.twoWayDataSyncedTableDescription'
        )
      } else if (table.is_data_sync) {
        return this.$t(
          'localBaserowTableSelector.oneWayDataSyncedTableDescription'
        )
      }
      return null
    },
    onTableSelect(tableId) {
      this.$emit('update:modelValue', tableId)
    },
  },
}
</script>
