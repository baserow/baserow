<template>
  <AggregateRowsDataSourceForm
    v-if="dataSource"
    ref="dataSourceForm"
    :dashboard="dashboard"
    :widget="widget"
    :data-source="dataSource"
    :default-values="dataSource"
    :store-prefix="storePrefix"
    :small="small"
    @values-changed="onDataSourceValuesChanged"
  />
</template>

<script>
import AggregateRowsDataSourceForm from '@baserow/modules/dashboard/components/data_source/AggregateRowsDataSourceForm'
import error from '@baserow/modules/core/mixins/error'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'SummaryWidgetSettings',
  components: { AggregateRowsDataSourceForm },
  mixins: [error],
  props: {
    excludeFilterWidgetId: { type: Number, default: null },
    small: {
      type: Boolean,
      default: true,
    },
    dashboard: {
      type: Object,
      required: true,
    },
    widget: {
      type: Object,
      required: true,
    },
    storePrefix: {
      type: String,
      required: false,
      default: '',
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  computed: {
    dataSource() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/getDataSourceById`
      ](this.widget.data_source_id)
    },
    integration() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/getIntegrationById`
      ](this.dataSource.integration_id)
    },
  },
  methods: {
    /** Validate all data settings before completing guided widget creation. */
    validate() {
      const form = this.$refs.dataSourceForm
      if (!form) return false
      form.touch(true)
      const valid = form.isFormValid(true)
      if (!valid) form.focusOnFirstError()
      return valid
    },
    async onDataSourceValuesChanged(changedDataSourceValues) {
      if (this.$refs.dataSourceForm.isFormValid()) {
        try {
          await this.$store.dispatch(
            `${this.storePrefix}dashboardApplication/updateDataSource`,
            {
              dataSourceId: this.dataSource.id,
              values: changedDataSourceValues,
              ...(this.excludeFilterWidgetId == null
                ? {}
                : { excludeFilterWidgetId: this.excludeFilterWidgetId }),
            }
          )
        } catch (error) {
          this.$refs.dataSourceForm.reset()
          this.$refs.dataSourceForm.touch()
          notifyIf(error, 'dashboard')
        }
      }
    },
  },
}
</script>
