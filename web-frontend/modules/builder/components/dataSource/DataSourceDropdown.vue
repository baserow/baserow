<template>
  <div>
    <p v-show="value === null" class="margin-bottom-1">
      <slot name="chooseValueState"></slot>
    </p>
    <Dropdown
      :value="value"
      class="data-source-dropdown"
      @input="$emit('input', $event)"
    >
      <DropdownItem
        v-for="dataSource in sharedDataSources"
        :key="dataSource.id"
        :name="getDataSourceLabel(dataSource)"
        :value="dataSource.id"
        icon="iconoir-multiple-pages-empty"
        :icon-tooltip="$t('dataSourceDropdown.shared')"
      >
      </DropdownItem>
      <template v-if="localDataSources">
        <DropdownItem
          v-for="dataSource in localDataSources"
          :key="dataSource.id"
          :name="getDataSourceLabel(dataSource)"
          :value="dataSource.id"
          icon="iconoir-empty-page"
          :icon-tooltip="$t('dataSourceDropdown.pageOnly')"
        >
        </DropdownItem
      ></template>
      <template #emptyState>
        <slot name="emptyState">
          {{
            isOnSharedPage
              ? $t('dataSourceDropdown.noSharedDataSources')
              : $t('dataSourceDropdown.noDataSources')
          }}
        </slot>
      </template>
    </Dropdown>
  </div>
</template>

<script>
export default {
  name: 'DataSourceDropdown',
  props: {
    value: {
      type: Number,
      required: false,
      default: null,
    },
    sharedDataSources: {
      type: Array,
      required: true,
    },
    localDataSources: {
      type: Array,
      required: false,
      default: null,
    },
    small: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    isOnSharedPage() {
      return this.localDataSources === null
    },
  },
  methods: {
    /**
     * Responsible for taking a data source object, and returning a
     * label for our data source dropdowns to use in their items. The
     * data source name is used, along with a suffix that indicates
     * whether the data source returns a single row or multiple rows.
     * @param dataSource - The data source object to generate a label for.
     * @returns {string} - The label to use in the dropdown.
     */
    getDataSourceLabel(dataSource) {
      if (dataSource.type === null) {
        // If the data source doesn't yet have a service type,
        // we just return the data source name, for now.
        return dataSource.name
      }
      const service = this.$registry.get('service', dataSource.type)
      const suffix = service.returnsList
        ? this.$t('integrationsCommon.multipleRows')
        : this.$t('integrationsCommon.singleRow')
      return `${dataSource.name} (${suffix})`
    },
  },
}
</script>
