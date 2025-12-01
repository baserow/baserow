<template>
  <ABFormGroup
    :label="resolvedLabel"
    :error-message="errorMessage"
    :autocomplete="isEditMode ? 'off' : ''"
    :required="element.required"
    :style="getStyleOverride('input')"
  >
    <ABInput
      v-model="computedValue"
      :placeholder="resolvedPlaceholder"
      :multiline="element.is_multiline"
      :rows="element.rows"
      :type="element.input_type"
      @blur="onFormElementTouch"
    />
  </ABFormGroup>
</template>

<script>
import formElement from '@baserow/modules/builder/mixins/formElement'
import {
  ensureNumeric,
  ensureString,
} from '@baserow/modules/core/utils/validator'
import { parseLocalizedNumber } from '@baserow/modules/core/utils/string'

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
    computedValue: {
      get() {
        return this.internalValue
      },
      set(newValue) {
        this.inputValue = this.fromInternalValue(newValue)
        this.internalValue = newValue
      },
    },
    localeLanguage() {
      return this.$i18n.locale
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
    inputValue: {
      handler(newValue) {
        // If the inputValue was updated (after a reset for instance) we want to update
        // the internal value
        if (this.fromInternalValue(this.internalValue) !== newValue) {
          this.internalValue = this.toInternalValue(newValue)
        }
      },
      immediate: true,
    },
  },
  methods: {
    toInternalValue(value) {
      if (this.isNumericField) {
        if (value) {
          return new Intl.NumberFormat(this.localeLanguage, {
            useGrouping: false,
          }).format(value)
        } else {
          return ''
        }
      }

      return ensureString(value)
    },

    fromInternalValue(value) {
      if (this.isNumericField) {
        if (value) {
          try {
            return ensureNumeric(
              parseLocalizedNumber(value, this.localeLanguage),
              {
                allowNull: true,
              }
            )
          } catch {
            return value
          }
        } else {
          return null
        }
      }
      return value
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
  },
}
</script>
