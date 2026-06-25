<template>
  <div>
    <DashboardWidget
      v-for="widget in widgets"
      :key="widget.id"
      v-sortable="{
        id: widget.id,
        update: orderWidgets,
        handle: '[data-sortable-handle]',
        enabled: canOrderWidgets,
        marginTop: -12,
        marginTopLast: 12,
      }"
      :widget="widget"
      :dashboard="dashboard"
      :store-prefix="storePrefix"
      :can-order-widgets="canOrderWidgets"
    />
  </div>
</template>

<script>
import DashboardWidget from '@baserow/modules/dashboard/components/widget/DashboardWidget'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'WidgetBoard',
  components: { DashboardWidget },
  props: {
    dashboard: {
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
    isEditMode() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/isEditMode`
      ]
    },
    widgets() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/getWidgets`
      ]
    },
    canOrderWidgets() {
      return (
        this.isEditMode &&
        this.$hasPermission(
          'dashboard.order_widgets',
          this.dashboard,
          this.dashboard.workspace.id
        )
      )
    },
  },
  methods: {
    async orderWidgets(order, oldOrder) {
      try {
        await this.$store.dispatch(
          `${this.storePrefix}dashboardApplication/orderWidgets`,
          {
            dashboard: this.dashboard,
            order,
            oldOrder,
          }
        )
      } catch (error) {
        notifyIf(error, 'dashboard')
      }
    },
  },
}
</script>
