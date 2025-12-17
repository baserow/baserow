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
        :value="value"
        :show-search="false"
        :disabled="databaseSelectedId === null"
        fixed-items
        :size="dropdownSize"
        @input="$emit('input', $event)"
      >
        <DropdownItem
          v-for="table in supportedServiceTables"
          :key="table.id"
          :name="table.name"
          :value="table.id"
          :description="getTableDescription(table)"
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
        :value="viewId"
        :show-search="false"
        :disabled="value === null"
        fixed-items
        :size="dropdownSize"
        @input="$emit('update:view-id', $event)"
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
    value: {
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
      return this.databaseSelected?.tables || []
    },
    supportedServiceTables() {
      return this.serviceType.supportedTables(this.tables)
    },
    views() {
      return (
        this.databaseSelected?.views.filter(
          (view) => view.table_id === this.value
        ) || []
      )
    },
  },
  watch: {
    value: {
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
  },
}
</script>
