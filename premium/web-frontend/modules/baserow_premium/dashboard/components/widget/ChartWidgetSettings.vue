<template>
  <GroupedAggregateRowsDataSourceForm
    v-if="dataSource && integration"
    ref="dataSourceForm"
    :dashboard="dashboard"
    :widget="widget"
    :data-source="dataSource"
    :default-values="dataSource"
    :store-prefix="storePrefix"
    :small="small"
    :show-own-filters="showOwnFilters"
    :loading="loading"
    @values-changed="onDataSourceValuesChanged"
    @widget-values-changed="widgetValuesChanged"
  />
</template>

<script>
import GroupedAggregateRowsDataSourceForm from '@baserow_premium/dashboard/components/data_source/GroupedAggregateRowsDataSourceForm'
import error from '@baserow/modules/core/mixins/error'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'ChartWidgetSettings',
  components: { GroupedAggregateRowsDataSourceForm },
  mixins: [error],
  props: {
    linkFilterWidgetId: { type: Number, default: null },
    /** Whether the widget's own filter conditions can be edited here. */
    showOwnFilters: {
      type: Boolean,
      default: true,
    },
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
      const aggSeries = changedDataSourceValues.aggregation_series
      if (
        aggSeries &&
        aggSeries.at(-1).id === undefined &&
        aggSeries.at(-1).field_id === null &&
        aggSeries.at(-1).aggregation_type === ''
      ) {
        // Loading state will be used for situations where a new
        // aggregation series needs widget configuration to be saved
        // before it is allowed to be changed.
        this.loading = true
      }
      try {
        await this.$store.dispatch(
          `${this.storePrefix}dashboardApplication/updateDataSource`,
          {
            dataSourceId: this.dataSource.id,
            values: changedDataSourceValues,
            ...(this.linkFilterWidgetId == null
              ? {}
              : { linkFilterWidgetId: this.linkFilterWidgetId }),
            widget: this.widget,
          }
        )
      } catch (error) {
        this.$refs.dataSourceForm.reset()
        this.$refs.dataSourceForm.touch()
        notifyIf(error, 'dashboard')
      } finally {
        this.loading = false
      }
    },
    async widgetValuesChanged(values) {
      try {
        await this.$store.dispatch(
          `${this.storePrefix}dashboardApplication/updateWidget`,
          {
            widgetId: this.widget.id,
            originalValues: this.widget,
            values,
          }
        )
      } catch (error) {
        notifyIf(error, 'dashboard')
      }
    },
  },
}
</script>
