<template>
  <div class="dashboard-chart-widget">
    <template v-if="!isDataLoading">
      <div
        class="dashboard-chart-widget__content widget__content"
        :class="{ 'loading-spinner': isChartLoading }"
      >
        <div
          class="dashboard-chart-widget__chart"
          :class="{
            'dashboard-chart-widget__chart--hidden': isChartLoading,
          }"
        >
          <Chart
            v-if="chartReady"
            :key="chartKey"
            :data-source="dataSource"
            :data-source-data="dataForDataSource"
            :series-config="widget.series_config"
            @rendered="chartRendered = true"
          >
          </Chart>
        </div>
      </div>
    </template>
    <div v-else class="dashboard-chart-widget__loading loading-spinner"></div>
  </div>
</template>

<script>
import Chart from '@baserow_premium/dashboard/components/widget/Chart'

export default {
  name: 'PieChartWidget',
  components: { Chart },
  data() {
    return {
      chartRendered: false,
    }
  },
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
    chartReady() {
      return Boolean(this.dataSource && this.dataForDataSource)
    },
    isDataLoading() {
      return this.loading || !this.chartReady
    },
    isChartLoading() {
      return !this.chartRendered
    },
    chartKey() {
      return `${this.dataSource?.id}-${JSON.stringify(
        this.dataForDataSource?.results || []
      )}`
    },
  },
  watch: {
    chartKey() {
      this.chartRendered = false
    },
  },
}
</script>
