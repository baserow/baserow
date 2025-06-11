<template>
  <GroupedAggregateRowsDataSourceForm
    v-if="dataSource && integration"
    ref="dataSourceForm"
    :dashboard="dashboard"
    :widget="widget"
    :data-source="dataSource"
    :default-values="dataSource"
    :store-prefix="storePrefix"
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
    async onDataSourceValuesChanged(changedDataSourceValues) {
      try {
        await this.$store.dispatch(
          `${this.storePrefix}dashboardApplication/updateDataSource`,
          {
            dataSourceId: this.dataSource.id,
            values: changedDataSourceValues,
            widget: this.widget,
          }
        )
      } catch (error) {
        this.$refs.dataSourceForm.reset()
        this.$refs.dataSourceForm.touch()
        notifyIf(error, 'dashboard')
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
