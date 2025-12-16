<template>
  <FormRow class="margin-bottom-2">
    <FormGroup
      :label="$t('localBaserowTableSelector.databaseFieldLabel')"
      small-label
      required
    >
      <Dropdown
        v-model="databaseSelectedId"
        :show-search="false"
        fixed-items
        :size="dropdownSize"
      >
        <DropdownItem
          v-for="database in databases"
          :key="database.id"
          :name="database.name"
          :value="database.id"
        >
          {{ database.name }}
        </DropdownItem>
      </Dropdown>
    </FormGroup>

    <FormGroup
      :label="$t('localBaserowTableSelector.tableFieldLabel')"
      small-label
      required
    >
      <Dropdown
        :model-value="modelValue"
        :show-search="false"
        :disabled="databaseSelectedId === null"
        fixed-items
        :size="dropdownSize"
        @update:model-value="onTableSelect"
      >
        <DropdownItem
          v-for="table in tables"
          :key="table.id"
          :name="table.name"
          :value="table.id"
          :description="
            table.is_data_sync
              ? $t('localBaserowTableSelector.dataSyncedTableDescription')
              : null
          "
        >
          {{ table.name }}
        </DropdownItem>
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
    viewId: {
      type: Number,
      required: false,
      default: null,
    },
    databases: {
      type: Array,
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
    disallowDataSyncedTables: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['update:modelValue', 'update:view-id'],
  data() {
    return {
      databaseSelectedId: null,
    }
  },
  computed: {
    databaseSelected() {
      return this.databases.find(
        (database) => database.id === this.databaseSelectedId
      )
    },
    tables() {
      return (
        this.databaseSelected?.tables.filter(
          (table) => !(this.disallowDataSyncedTables && table.is_data_sync)
        ) || []
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
  watch: {
    modelValue: {
      handler(tableId) {
        if (tableId !== null) {
          const databaseOfTableId = this.databases.find((database) =>
            database.tables.some((table) => table.id === tableId)
          )
          if (databaseOfTableId) {
            this.databaseSelectedId = databaseOfTableId.id
          }
        }
      },
      immediate: true,
    },
  },
  methods: {
    onTableSelect(tableId) {
      this.$emit('update:modelValue', tableId)
    },
  },
}
</script>
