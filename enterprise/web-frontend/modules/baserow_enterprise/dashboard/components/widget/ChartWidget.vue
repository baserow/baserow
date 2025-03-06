<template>
  <div class="dashboard-chart-widget">
    <div class="widget__header">
      <div class="widget__header-main">
        <div class="widget__header-title-wrapper">
          <div class="widget__header-title">{{ widget.title }}</div>

          <Badge
            v-if="dataSourceMisconfigured"
            color="red"
            size="small"
            indicator
            rounded
            >{{ $t('widget.fixConfiguration') }}</Badge
          >
        </div>
        <div v-if="widget.description" class="widget__header-description">
          {{ widget.description }}
        </div>
      </div>
      <WidgetContextMenu
        v-if="isEditMode"
        :widget="widget"
        :dashboard="dashboard"
        @delete-widget="$emit('delete-widget', $event)"
      ></WidgetContextMenu>
    </div>

    <div class="dashboard-chart-widget__content widget__content">
      <Chart
        v-if="!loading"
        :data-source="dataSource"
        :data-source-data="dataForDataSource"
      >
      </Chart>

      <div v-else class="dashboard-chart-widget__loading loading-spinner"></div>
    </div>
  </div>
</template>

<script>
import WidgetContextMenu from '@baserow/modules/dashboard/components/widget/WidgetContextMenu'
import Chart from '@baserow_enterprise/dashboard/components/widget/Chart'

export default {
  name: 'ChartWidget',
  components: { WidgetContextMenu, Chart },
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
    isEditMode() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/isEditMode`
      ]
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
