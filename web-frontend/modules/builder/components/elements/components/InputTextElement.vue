<template>
  <ABFormGroup
    :label="resolvedLabel"
    :error-message="errorMessage"
    :autocomplete="isEditMode ? 'off' : ''"
    :required="element.required"
    :style="getStyleOverride('input')"
  >
    <ABInput
      :value="internalValue"
      :placeholder="resolvedPlaceholder"
      :multiline="element.is_multiline"
      :rows="element.rows"
      :type="element.input_type"
      @blur="handleBlur"
      @focus="handleFocus"
      @input="handleInput"
    />
  </ABFormGroup>
</template>

<script>
import formElement from '@baserow/modules/builder/mixins/formElement'
import {
  ensureNumeric,
  ensureString,
} from '@baserow/modules/core/utils/validator'

export default {
  name: 'InputTextElement',
  mixins: [formElement],
  props: {
    /**
     * @type {Object}
     * @property {string} default_value - The text input's default value.
     * @property {boolean} required - Whether the text input is required.
     * @property {Object} placeholder - The text input's placeholder value.
     * @property {boolean} multiline - Whether the text input is multiline.
     * @property {number} rows - The number of rows (height) of the input.
     */
    element: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      internalValue: '',
    }
  },
  computed: {
    localeLanguage() {
      return process.client ? navigator.language : this.$i18n.locale
    },
    decimalSeparator() {
      return new Intl.NumberFormat(this.localeLanguage).format(1.1).charAt(1)
    },
    thousandSeparator() {
      return this.decimalSeparator === '.' ? ',' : '.'
    },
    resolvedDefaultValue() {
      return this.handleInputValue(
        ensureString(this.resolveFormula(this.element.default_value))
      )
    },
    isNumericField() {
      return this.element.validation_type === 'integer'
    },
    resolvedLabel() {
      return ensureString(this.resolveFormula(this.element.label))
    },
    resolvedPlaceholder() {
      return ensureString(this.resolveFormula(this.element.placeholder))
    },
  },
  watch: {
    resolvedDefaultValue: {
      handler(value) {
        if (!this.inputValue) {
          this.inputValue = this.handleInputValue(value)
          this.updateInternalValue()
        }
      },
      immediate: true,
    },
  },
  methods: {
    updateInternalValue() {
      // Format the model value for display in the input
      if (this.isNumericField && this.inputValue !== null) {
        this.internalValue = this.formatNumericValueForDisplay(this.inputValue)
      } else {
        this.internalValue = this.inputValue || ''
      }
    },

    handleInputValue(value) {
      try {
        return this.isNumericField
          ? ensureNumeric(value, { allowNull: true })
          : ensureString(value)
      } catch (e) {
        return ensureString(value)
      }
    },

    handleInput(value) {
      // Update internal value as user types
      this.internalValue = value

      // For non-numeric fields, we can update the model immediately
      if (!this.isNumericField) {
        this.inputValue = value
      }
    },

    toStoreNumericValue(value) {
      const decimalSeparator =
        this.decimalSeparator === '.' ? '\\.' : this.decimalSeparator
      const thousandSeparator =
        this.thousandSeparator === '.' ? '\\.' : this.thousandSeparator

      if (typeof value === 'number') {
        return value
      }
      if (!value) {
        return null
      }
      try {
        const cleanedValue = value
          .replace(new RegExp(`[${thousandSeparator} ]`, 'g'), '')
          .replace(new RegExp(decimalSeparator, 'g'), '.')
        return ensureNumeric(cleanedValue, { allowNull: true })
      } catch (e) {
        return value
      }
    },

    formatNumericValueForDisplay(value) {
      if (isNaN(Number(value))) {
        return value
      }
      try {
        return new Intl.NumberFormat(this.localeLanguage, {
          maximumFractionDigits: 20,
          // TODO: Make thousand grouping configurable?
          useGrouping: true,
        }).format(Number(value))
      } catch (e) {
        return value
      }
    },

    getErrorMessage() {
      switch (this.element.validation_type) {
        case 'integer':
          return this.$t('error.invalidNumber')
        case 'email':
          return this.$t('error.invalidEmail')
        default:
          return this.$t('error.requiredField')
      }
    },

    handleBlur() {
      // For numeric fields, convert the display value to a numeric value for the model
      if (this.isNumericField) {
        try {
          const numericValue = this.toStoreNumericValue(this.internalValue)
          this.inputValue = numericValue
          // Update the internal value to show properly formatted number
          this.updateInternalValue()
        } catch (e) {
          console.warn('Failed to convert input to numeric value', e)
        }
      }
      this.onFormElementTouch()
    },

    handleFocus() {
      // For numeric fields, we want to show the raw value without formatting
      if (this.isNumericField && this.inputValue !== null) {
        this.internalValue = String(this.inputValue).replace(
          '.',
          this.decimalSeparator
        )
      }
    },
  },
}
</script>
