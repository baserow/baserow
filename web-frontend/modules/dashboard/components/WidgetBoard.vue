<template>
  <div>
    <DashboardWidget
      v-for="widget in widgets"
      :key="widget.id"
      :widget="widget"
      :dashboard="dashboard"
      :store-prefix="storePrefix"
    />
  </div>
</template>

<script>
import DashboardWidget from '@baserow/modules/dashboard/components/widget/DashboardWidget'

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
  },
}
</script>
