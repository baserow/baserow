<template>
  <div class="dashboard-summary-widget">
    <template v-if="!loading">
      <div
        class="widget__content dashboard-summary-widget__summary"
        :class="{
          'dashboard-summary-widget__summary--misconfigured':
            dataSourceMisconfigured,
        }"
      >
        {{ result }}
      </div>
    </template>
  </div>
</template>

<script>
export default {
  name: 'SummaryWidget',
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
    result() {
      if (this.dataSource) {
        const data = this.dataForDataSource
        if (data && data.result !== undefined) {
          const serviceType = this.$registry.get(
            'service',
            this.dataSource.type
          )
          // A sum over no matching rows is null in SQL; show the empty total as zero.
          const resultData =
            this.dataSource.aggregation_type === 'sum' && data.result === null
              ? { ...data, result: 0 }
              : data
          return serviceType.getResult(this.dataSource, resultData)
        }
      }
      return 0
    },
    dataSourceMisconfigured() {
      const data = this.dataForDataSource
      if (data) {
        return !!data._error
      }
      return false
    },
  },
}
</script>
