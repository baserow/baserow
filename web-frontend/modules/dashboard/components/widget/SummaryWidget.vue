<template>
  <div class="dashboard-summary-widget">
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
    <div
      class="dashboard-summary-widget__summary"
      :class="{
        'dashboard-summary-widget__summary--misconfigured':
          dataSourceMisconfigured,
      }"
    >
      {{ result }}
    </div>
  </div>
</template>

<script>
import WidgetContextMenu from '@baserow/modules/dashboard/components/widget/WidgetContextMenu'

export default {
  name: 'SummaryWidget',
  components: { WidgetContextMenu },
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
    result() {
      if (this.dataSource) {
        const data = this.dataForDataSource
        if (data && data.result !== undefined) {
          const serviceType = this.$registry.get(
            'service',
            this.dataSource.type
          )
          return serviceType.getResult(this.dataSource, data)
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
