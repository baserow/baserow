import { DurationFieldType } from '@baserow/modules/database/fieldTypes'
import { formatDurationValue } from '@baserow/modules/database/utils/duration'

/**
 * This mixin contains some method overrides for validating and formatting the
 * duration field. This mixin is used in both the GridViewFieldDuration and
 * RowEditFieldDuration components.
 */
export default {
  data() {
    return {
      errorMsg: null,
      formattedValue: '',
    }
  },
  watch: {
    value(value) {
      this.updateFormattedValue(this.field, value)
    },
  },
  created() {
    this.updateFormattedValue(this.field, this.value)
  },
  methods: {
    getField() {
      return this.field
    },
    getError() {
      // `errorMsg` holds the parse error captured while the user types, because
      // partially-typed text may not round-trip to `value`. A valid parsed copy
      // is not emitted as `value` until blur, so validate that copy while editing.
      const value = this.editing ? this.prepareValue(this.copy) : this.value
      return this.errorMsg ?? this.getValidationError(value)
    },
    formatValue(field, value) {
      // This function is used also in functional components,
      // so we cannot get the field type from the registry here.
      return formatDurationValue(value, field.duration_format)
    },
    updateFormattedValue(field, value) {
      this.formattedValue = this.formatValue(field, value)
    },
    updateCopy(field, value) {
      this.errorMsg = this.getValidationError(value)
      if (this.errorMsg !== null) {
        return
      }
      const fieldType = this.$registry.get('field', DurationFieldType.getType())
      const newCopy = fieldType.parseInputValue(field, value)
      if (newCopy !== this.copy) {
        this.copy = newCopy
        return newCopy
      }
    },
    isValidChar(char) {
      const allowedChars = ['.', ':', ' ', 'd', 'h', 'm', 's', '-']
      return /\d/.test(char) || allowedChars.includes(char)
    },
    onKeyPress(field, event) {
      if (!this.isValidChar(event.key)) {
        return event.preventDefault()
      }
    },
    onInput(field, event) {
      this.updateCopy(field, event.target.value)
    },
  },
}
