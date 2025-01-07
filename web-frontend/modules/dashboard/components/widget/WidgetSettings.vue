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
      :store-prefix="storePrefix"
    />
  </div>
</template>

<script>
import _ from 'lodash'
import WidgetSettingsBaseForm from '@baserow/modules/dashboard/components/widget/WidgetSettingsBaseForm'
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
    storePrefix: {
      type: String,
      required: false,
      default: '',
    },
  },
  computed: {
    widgetType() {
      return this.$registry.get('dashboardWidget', this.widget.type)
    },
    widgetSettingsComponent() {
      return this.widgetType.settingsComponent
    },
  },
  methods: {
    async baseFormValuesChanged(values) {
      if (this.$refs.form.isFormValid()) {
        const defaultValues = this.$refs.form.defaultValues
        const originalValues = JSON.parse(JSON.stringify(defaultValues))
        const defaultWithUpdatedValues = { ...defaultValues, ...values }

        // Compute only the values in the form that has been actually
        // changed
        const updatedValues = Object.fromEntries(
          Object.entries(defaultWithUpdatedValues).filter(
            ([key, value]) => !_.isEqual(value, defaultValues[key])
          )
        )
        try {
          await this.$store.dispatch(
            `${this.storePrefix}dashboardApplication/updateWidget`,
            {
              widgetId: this.widget.id,
              values: updatedValues,
              originalValues,
            }
          )
        } catch (error) {
          notifyIf(error, 'dashboard')
        }
      }
    },
  },
}
</script>
