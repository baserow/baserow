<template>
  <div>
    <p v-show="value === null" class="margin-bottom-1">
      <slot name="chooseValueState"></slot>
    </p>
    <Dropdown
      :value="value"
      show-footer
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
      <template #footer>
        <a class="select__footer-button" @click="openDataSourceModal">
          <i class="iconoir-plus"></i>
          {{ $t('dataSourceDropdown.addNew') }}
        </a>
      </template>
    </Dropdown>
    <DataSourceCreateEditModal
      :key="modalKey"
      ref="dataSourceCreateEditModal"
      @updated="onDataSourceUpdated"
    />
  </div>
</template>

<script>
import DataSourceCreateEditModal from '@baserow/modules/builder/components/dataSource/DataSourceCreateEditModal'

export default {
  name: 'DataSourceDropdown',
  components: { DataSourceCreateEditModal },
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
  data() {
    return {
      modalKey: 0,
    }
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
    openDataSourceModal() {
      this.$refs.dataSourceCreateEditModal.show()
    },
    /**
     * When a data source is updated (i.e. the user has created the record,
     * *and* updated it), we want to check if it has a valid schema. If it does,
     * we emit the input event so that the dropdown updates to select the newly
     * created data source.
     * @param dataSource - The updated data source.
     */
    onDataSourceUpdated(dataSource) {
      const serviceType =
        dataSource.type && this.$registry.get('service', dataSource.type)
      if (serviceType?.getDataSchema(dataSource)) {
        this.modalKey++
        this.$emit('input', dataSource.id)
      }
    },
  },
}
</script>
