<template>
  <ABFormGroup
    :label="resolvedLabel"
    :error-message="errorMessage"
    :autocomplete="isEditMode ? 'off' : ''"
    :required="element.required"
    :style="getStyleOverride('input')"
  >
    <ABInput
      v-model="inputValue"
      :placeholder="resolvedPlaceholder"
      :multiline="element.is_multiline"
      :rows="element.rows"
      :type="element.input_type"
      :to-value="toStoreValue"
      :from-value="toDisplayValue"
      @blur="handleBlur"
      @focus="handleFocus"
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
    element: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      isFocused: false,
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
      // when we have inputValue watcher, this isn't actually needed
      // we use it to avoid delay in showing default value
      handler(value) {
        if (!this.inputValue) {
          this.inputValue = this.handleInputValue(value)
        }
      },
      immediate: true,
    },
    inputValue: {
      // when we have resolvedDefaultValue watcher, this shouldn't be needed
      // but, getInitialFormDataValue is called after our resolvedDefaultValue
      // which overwrites the numeric inputValue with a string value
      handler(value) {
        const processedInputValue = this.handleInputValue(value)
        if (!this.inputValue || this.inputValue !== processedInputValue) {
          this.inputValue = processedInputValue
        }
      },
      immediate: true,
    },
  },
  methods: {
    handleInputValue(value) {
      try {
        return this.isNumericField
          ? ensureNumeric(value, { allowNull: true })
          : ensureString(value)
      } catch (e) {
        return ensureString(value)
      }
    },
    // Convert display value (what user types) to store value
    toStoreValue(value) {
      return this.isNumericField ? this.toStoreNumericValue(value) : value
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

    // Convert store value to display value
    toDisplayValue(value) {
      if (!this.isNumericField || !value) {
        return value
      }
      return this.toDisplayNumericValue(value)
    },
    toDisplayNumericValue(value) {
      if (isNaN(Number(value))) {
        return value
      }
      if (this.isFocused) {
        // Convert to string with local decimal separator
        return String(value).replace('.', this.decimalSeparator)
      }
      // When not focused, format the number (optionally with local thousand separator)
      try {
        return new Intl.NumberFormat(this.localeLanguage, {
          maximumFractionDigits: 20,
          // TODO: Make thousand grouping configurable
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
      this.isFocused = false
      // this.inputValue = this.toStoreValue(this.inputValue)
      this.onFormElementTouch()
    },

    handleFocus() {
      this.isFocused = true
      // this.inputValue = this.toStoreValue(this.inputValue)
    },
  },
}
</script>
