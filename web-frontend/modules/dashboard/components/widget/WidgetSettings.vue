<template>
  <div>
    <WidgetSettingsBaseForm
      ref="form"
      :widget="widget"
      :default-values="widget"
      @values-changed="baseFormValuesChanged($event)"
    />
    <component
      :is="widgetSettingsComponent"
      :dashboard="dashboard"
      :widget="widget"
    />
  </div>
</template>

<script>
import WidgetSettingsBaseForm from '@baserow/modules/dashboard/components/widget/WidgetSettingsBaseForm'
import { mapActions } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'WidgetSettings',
  components: { WidgetSettingsBaseForm },
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
    widget: {
      type: Object,
      required: true,
    },
  },
  computed: {
    widgetType() {
      return this.$registry.get('dashboard_widget', this.widget.type)
    },
    widgetSettingsComponent() {
      return this.widgetType.settingsComponent
    },
  },
  methods: {
    ...mapActions({
      updateWidget: 'dashboardApplication/updateWidget',
    }),
    async baseFormValuesChanged(values) {
      if (this.$refs.form.isFormValid()) {
        try {
          await this.updateWidget({ widgetId: this.widget.id, values })
        } catch (error) {
          notifyIf(error, 'dashboard')
        }
      }
    },
  },
}
</script>
