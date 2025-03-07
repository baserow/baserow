<template>
  <div
    class="dashboard-summary-widget"
    :class="{
      'dashboard-summary-widget--with-header-description': widget.description,
    }"
  >
    <template v-if="!loading">
      <div class="widget__header widget__header--no-border">
        <div class="widget__header-main">
          <div class="widget__header-title-wrapper">
            <div class="widget__header-title">{{ widget.title }}</div>

            <Badge
              v-if="dataSourceMisconfigured"
              color="red"
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
    <div v-else class="dashboard-summary-widget__loading loading-spinner"></div>
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
