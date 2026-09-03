<template>
  <div class="dashboard-chart-widget">
    <template v-if="!loading">
      <div class="dashboard-chart-widget__content widget__content">
        <Chart
          :data-source="dataSource"
          :data-source-data="dataForDataSource"
          :series-config="widget.series_config"
        >
        </Chart>
      </div>
    </template>
    <div v-else class="dashboard-chart-widget__loading loading-spinner"></div>
  </div>
</template>

<script>
import Chart from '@baserow_premium/dashboard/components/widget/Chart'

export default {
  name: 'ChartWidget',
  components: { Chart },
  props: {
    widget: {
      type: Object,
      required: true,
    },
    storePrefix: {
      type: String,
      required: false,
      default: '',
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    dataSource() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/getDataSourceById`
      ](this.widget.data_source_id)
    },
    dataForDataSource() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/getDataForDataSource`
      ](this.dataSource?.id)
    },
  },
}
</script>
