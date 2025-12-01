<template>
  <ABFormGroup
    :label="resolvedLabel"
    :error-message="errorMessage"
    :required="element.required"
    :style="getStyleOverride('input')"
  >
    <ABDateTimePicker
      ref="datePicker"
      v-model="inputValue"
      :date-format="DATE_FORMATS[element.date_format].format"
      :time-format="TIME_FORMATS[element.time_format].format"
      :include-time="element.include_time"
      :calendar-style="getStyleOverride('input')"
      :clock-style="getStyleOverride('input')"
    ></ABDateTimePicker>
  </ABFormGroup>
</template>

<script>
import formElement from '@baserow/modules/builder/mixins/formElement'
import ABDateTimePicker from '@baserow/modules/builder/components/elements/baseComponents/ABDateTimePicker.vue'
import { DATE_FORMATS, TIME_FORMATS } from '@baserow/modules/builder/enums'
import { ensureString } from '@baserow/modules/core/utils/validator'

export default {
  name: 'DateTimePickerElement',
  components: { ABDateTimePicker },
  mixins: [formElement],
  props: {
    /**
     * @type {Object}
     * @property {string} default_value - The date picker default value.
     * @property {boolean} required - Whether this form field is required.
     * @property {string} date_format - EU (25/04/2024), US (04/25/2024) or ISO (2024-04-25)
     * @property {boolean} include_time - Whether to include time in the representation of the date.
     * @property {string} time_format - 24 (14:00) or 12 (02:30) PM
     */
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {
    TIME_FORMATS() {
      return TIME_FORMATS
    },
    DATE_FORMATS() {
      return DATE_FORMATS
    },
    resolvedLabel() {
      return ensureString(this.resolveFormula(this.element.label))
    },
  },
  methods: {
    getErrorMessage() {
      if (this.inputValue) {
        return this.$t('dateTimePickerElementForm.invalidDateError')
      }
      return this.$t('error.requiredField')
    },
  },
}
</script>
