<template>
  <div
    class="dashboard-chart-widget"
    :class="{
      'dashboard-chart-widget--with-header-description': widget.description,
    }"
  >
    <template v-if="!loading">
      <div
        class="widget__header"
        :class="{
          'widget__header--edit-mode': editMode,
        }"
      >
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
import WidgetContextMenu from '@baserow/modules/dashboard/components/widget/WidgetContextMenu'
import Chart from '@baserow_premium/dashboard/components/widget/Chart'

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
    editMode: {
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
