import BigNumber from 'bignumber.js'
import {
  formatNumberValue,
  parseNumberValue,
  getNumberFormatOptions,
} from '@baserow/modules/database/utils/number'

/**
 * This mixin contains some method overrides for validating and formatting the
 * number field. This mixin is used in both the GridViewFieldNumber and
 * RowEditFieldNumber components. All methods requires the field to be passed as
 * they can be used in functional components.
 */
export default {
  data() {
    return {
      formattedValue: '',
      focused: false,
      roundDecimals: true,
    }
  },
  methods: {
    updateFormattedValue(field, value) {
      this.formattedValue = this.formatNumberValue(field, value)
    },
    formatNumberValue(field, value) {
      return formatNumberValue(field, value, true, this.roundDecimals)
    },
    /*
     * This method is similar to formatNumberValue, but it returns the value as a
     * string without the number prefix, suffix and thousand separator. This is
     * useful when the value is being edited and the user should only see the
     * decimal separator.
     */
    formatNumberValueForEdit(field, value) {
      const withThousandSeparator = false
      return formatNumberValue(
        field,
        value,
        withThousandSeparator,
        this.roundDecimals
      )
    },
    parseNumberValue(field, value) {
      return parseNumberValue(field, value, this.roundDecimals)
    },
    getNumberFormatOptions(field) {
      return getNumberFormatOptions(field)
    },
    onInput(field, event) {
      this.updateCopy(field, event.target.value)
    },
    onFocus() {
      this.focused = true
      this.copy = this.formatNumberValueForEdit(this.field, this.copy)
    },
    onBlur() {
      this.focused = false
      this.updateFormattedValue(this.field, this.copy)
    },
    onKeyPress(event) {
      if (!this.isValidChar(event.key)) {
        return event.preventDefault()
      }
    },
    isValidChar(char) {
      const validChars = []
      if (this.field.number_negative) {
        validChars.push('-')
      }
      // Allow any non-digit character in the number prefix and suffix.
      const {
        numberPrefix,
        numberSuffix,
        decimalSeparator,
        thousandSeparator,
      } = this.getNumberFormatOptions(this.field)
      validChars.push(...numberPrefix.split(''), ...numberSuffix.split(''))
      // Allow the decimal separator and the thousands separator.
      validChars.push(decimalSeparator, thousandSeparator)
      return /\d/.test(char) || validChars.includes(char)
    },
    prepareCopy(value) {
      // FIXME: This function is called with value that can be either a number or the string
      // representation of a number. It if's a string, it's not in the field format, so
      // we need to parse it first
      if (value == null || value === '') {
        return ''
      }
      return this.formatNumberValueForEdit(this.field, new BigNumber(value))
    },
    prepareValue(copy) {
      return this.parseNumberValue(this.field, copy)
    },
    beforeSave(copy) {
      return this.parseNumberValue(this.field, copy)
    },
    afterSave(value) {
      this.updateFormattedValue(this.field, this.prepareCopy(value))
    },
    getStartEditIndex(field, value) {
      if (value == null || value === '') {
        return 0
      }

      const { decimalSeparator, numberSuffix } =
        this.getNumberFormatOptions(field)
      const decimalSeparatorIndex = value.indexOf(decimalSeparator)
      const suffixIndex = numberSuffix ? value.indexOf(numberSuffix) : -1
      return decimalSeparatorIndex !== -1
        ? decimalSeparatorIndex
        : suffixIndex !== -1
        ? suffixIndex
        : value.length
    },
    updateCopy(field, newCopy) {
      if (newCopy == null || newCopy === '') {
        this.copy = ''
        return
      }
      const newNumber = this.parseNumberValue(field, newCopy)
      const prevNumber = this.parseNumberValue(field, this.copy)
      if (newNumber !== prevNumber) {
        this.copy = newCopy
      }
    },
  },
}
