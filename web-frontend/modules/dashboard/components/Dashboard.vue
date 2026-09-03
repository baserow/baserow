<template>
  <div class="dashboard-app">
    <DashboardHeader
      :dashboard="dashboard"
      :is-creating-widget="isCreatingWidget"
      :store-prefix="storePrefix"
      @widget-variation-selected="createWidget"
    />
    <DashboardContent
      :dashboard="dashboard"
      :is-creating-widget="isCreatingWidget"
      :store-prefix="storePrefix"
      @widget-variation-selected="createWidget"
    />
  </div>
</template>

<script>
import DashboardHeader from '@baserow/modules/dashboard/components/DashboardHeader'
import DashboardContent from '@baserow/modules/dashboard/components/DashboardContent'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'Dashboard',
  components: { DashboardHeader, DashboardContent },
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
  data() {
    return {
      isCreatingWidget: false,
    }
  },
  methods: {
    async createWidget(widgetVariation) {
      if (this.isCreatingWidget) {
        return
      }

      const widgetType = widgetVariation.type.getType()
      const typeFromRegistry = this.$registry.get('dashboardWidget', widgetType)
      this.isCreatingWidget = true
      try {
        await this.$store.dispatch(
          `${this.storePrefix}dashboardApplication/createWidget`,
          {
            dashboard: this.dashboard,
            widget: {
              title: typeFromRegistry.name,
              type: widgetType,
              ...widgetVariation.params,
            },
          }
        )
        await this.$store.dispatch(
          `${this.storePrefix}dashboardApplication/enterEditMode`
        )
      } catch (error) {
        notifyIf(error, 'dashboard')
      } finally {
        this.isCreatingWidget = false
      }
    },
  },
}
</script>
