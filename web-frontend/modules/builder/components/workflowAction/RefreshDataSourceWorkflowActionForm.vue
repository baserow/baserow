<template>
  <form @submit.prevent>
    <FormGroup
      :label="$t('tableElementForm.dataSource')"
      small-label
      required
      class="margin-bottom-2"
    >
      <div class="control__elements">
        <DataSourceDropdown
          v-model="values.data_source_id"
          small
          :shared-data-sources="sharedDataSources"
          :local-data-sources="localDataSources"
        >
        </DataSourceDropdown>
      </div>
    </FormGroup>
  </form>
</template>

<script>
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import DataSourceDropdown from '@baserow/modules/builder/components/dataSource/DataSourceDropdown'

export default {
  name: 'RefreshDataSourceWorkflowActionForm',
  components: { DataSourceDropdown },
  mixins: [elementForm],
  props: {
    workflowAction: {
      type: Object,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      allowedValues: ['data_source_id'],
      values: {
        data_source_id: null,
      },
    }
  },
  computed: {
    sharedPage() {
      return this.$store.getters['page/getSharedPage'](this.builder)
    },
    /**
     * Returns all data sources that are available not on shared page.
     * @returns {Array} - The data sources the page designer can choose from.
     */
    localDataSources() {
      if (this.elementPage.id === this.sharedPage.id) {
        // If the element is on the shared page they are no local page but only
        // shared page.
        return null
      } else {
        return this.$store.getters['dataSource/getPagesDataSources']([
          this.elementPage,
        ]).filter((dataSource) => dataSource.type)
      }
    },
    /**
     * Returns the shared data sources.
     * @returns {Array} - The shared data sources the page designer can choose from.
     */
    sharedDataSources() {
      // We keep only data sources that have a type and a schema.
      return this.$store.getters['dataSource/getPagesDataSources']([
        this.sharedPage,
      ]).filter(
        (dataSource) =>
          dataSource.type &&
          this.$registry
            .get('service', dataSource.type)
            .getDataSchema(dataSource)
      )
    },
  },
}
</script>
