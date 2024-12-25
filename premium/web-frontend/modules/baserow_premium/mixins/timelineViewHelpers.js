import {
  getDateField,
  dateSettinsAreValid,
} from '@baserow_premium/utils/timeline'
import { getFieldTimezone } from '@baserow/modules/database/utils/date'

export default {
  props: {
    database: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    storePrefix: {
      type: String,
      required: true,
      default: '',
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  computed: {
    timezone() {
      const tz = this.startDateField
        ? getFieldTimezone(this.startDateField)
        : null
      return tz || 'UTC'
    },
    canChangeDateSettings() {
      return (
        !this.readOnly &&
        this.$hasPermission(
          'database.table.view.update',
          this.view,
          this.database.workspace.id
        )
      )
    },
    startDateField() {
      const fieldId = this.view.start_date_field
      return getDateField(this.$registry, this.fields, fieldId)
    },
    endDateField() {
      const fieldId = this.view.end_date_field
      return getDateField(this.$registry, this.fields, fieldId)
    },
    dateSettingsAreValid() {
      return dateSettinsAreValid(this.startDateField, this.endDateField)
    },
  },
}
