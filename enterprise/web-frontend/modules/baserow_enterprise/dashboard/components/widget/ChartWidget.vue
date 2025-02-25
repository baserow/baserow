<template>
  <div class="dashboard-chart-widget">
    <div class="widget-header">
      <div class="widget-header__main">
        <div class="widget-header__title-wrapper">
          <div class="widget-header__title">{{ widget.title }}</div>
          <div
            v-if="dataSourceMisconfigured"
            class="widget-header__fix-configuration"
          >
            <svg
              width="5"
              height="6"
              viewBox="0 0 5 6"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <circle cx="2.5" cy="3" r="2.5" fill="#FF5A44" />
            </svg>
            {{ $t('widget.fixConfiguration') }}
          </div>
        </div>
        <div v-if="widget.description" class="widget-header__description">
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
    <Chart :data-source="dataSource" :data-source-data="dataForDataSource">
    </Chart>
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
