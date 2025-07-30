<template>
  <div>
    <FormGroup
      small-label
      :error="fieldHasErrors('number_decimal_places')"
      :label="$t('fieldNumberSubForm.decimalPlacesLabel')"
      class="margin-bottom-2"
      required
    >
      <Dropdown
        v-model="v$.values.number_decimal_places.$model"
        :error="fieldHasErrors('number_decimal_places')"
        :fixed-items="true"
        @hide="v$.values.number_decimal_places.$touch"
      >
        <DropdownItem name="0 (1)" :value="0"></DropdownItem>
        <DropdownItem name="1 (1.0)" :value="1"></DropdownItem>
        <DropdownItem name="2 (1.00)" :value="2"></DropdownItem>
        <DropdownItem name="3 (1.000)" :value="3"></DropdownItem>
        <DropdownItem name="4 (1.0000)" :value="4"></DropdownItem>
        <DropdownItem name="5 (1.00000)" :value="5"></DropdownItem>
        <DropdownItem name="6 (1.000000)" :value="6"></DropdownItem>
        <DropdownItem name="7 (1.0000000)" :value="7"></DropdownItem>
        <DropdownItem name="8 (1.00000000)" :value="8"></DropdownItem>
        <DropdownItem name="9 (1.000000000)" :value="9"></DropdownItem>
        <DropdownItem name="10 (1.0000000000)" :value="10"></DropdownItem>
      </Dropdown>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('fieldNumberSubForm.prefixAndSuffixLabel')"
      class="margin-bottom-2"
    >
      <div class="flex">
        <FormInput
          v-model="v$.values.number_prefix.$model"
          :error="fieldHasErrors('number_prefix')"
          type="text"
          :placeholder="$t('fieldNumberSubForm.prefixPlaceholder')"
        ></FormInput>
        <FormInput
          v-model="v$.values.number_suffix.$model"
          :error="fieldHasErrors('number_suffix')"
          type="text"
          :placeholder="$t('fieldNumberSubForm.suffixPlaceholder')"
          @blur="v$.values.number_suffix.$touch"
        ></FormInput>
      </div>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('fieldNumberSubForm.separatorLabel')"
      :class="{ 'margin-bottom-2': allowSetNumberNegative }"
    >
      <Dropdown v-model="v$.values.number_separator.$model" :fixed-items="true">
        <DropdownItem
          v-for="option in numberFormatOptions"
          :key="option.value"
          :name="option.name"
          :value="option.value"
        />
      </Dropdown>
    </FormGroup>

    <FormGroup class="margin-bottom-2">
      <Checkbox
        v-if="allowSetNumberNegative"
        v-model="v$.values.number_negative.$model"
        >{{ $t('fieldNumberSubForm.allowNegative') }}</Checkbox
      >
    </FormGroup>

    <FormGroup small-label :label="$t('fieldNumberSubForm.defaultValueLabel')">
      <FormInput
        v-model="formattedDefaultValue"
        :error="fieldHasErrors('number_default')"
        type="text"
        :placeholder="$t('fieldNumberSubForm.defaultValuePlaceholder')"
        :disabled="isDefaultValueFieldDisabled"
        @focus="onDefaultValueFocus"
        @blur="onDefaultValueBlur"
        @keypress="onKeyPress"
      ></FormInput>
      <div
        v-if="isDefaultValueFieldDisabled"
        class="control__messages padding-top-0"
      >
        <p
          class="control__helper-text control__helper-text--warning field-context__inner-element-width"
        >
          {{ $t('fieldForm.defaultValueDisabledByConstraint') }}
        </p>
      </div>
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, maxLength } from '@vuelidate/validators'
import BigNumber from 'bignumber.js'
import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import numberField from '@baserow/modules/database/mixins/numberField'
import { NUMBER_FORMATS } from '@baserow/modules/database/utils/number'

export default {
  name: 'FieldNumberSubForm',
  mixins: [form, fieldSubForm, numberField],
  props: {
    allowSetNumberNegative: {
      type: Boolean,
      required: false,
      default: true,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    let allowedValues = [
      'number_decimal_places',
      'number_prefix',
      'number_suffix',
      'number_separator',
      'number_default',
    ]
    let values = {
      number_decimal_places: 0,
      number_separator: NUMBER_FORMATS.NO_FORMATTING.value,
      number_prefix: '',
      number_suffix: '',
      number_default: '',
    }

    if (this.allowSetNumberNegative) {
      allowedValues = [...allowedValues, 'number_negative']
      values = { ...values, number_negative: false }
    }

    return {
      allowedValues,
      values,
      focused: false,
      formattedDefaultValue: '',
    }
  },
  computed: {
    numberFormatOptions() {
      return Object.entries(NUMBER_FORMATS).map(([key, format]) => ({
        name: this.$t(format.description),
        value: format.value,
      }))
    },
    /**
     * Map the values to the field property, so that they work with in combination
     * with the helper methods in the `numberField` mixin.
     */
    field() {
      return {
        number_decimal_places: this.values.number_decimal_places,
        number_prefix: this.values.number_prefix,
        number_suffix: this.values.number_suffix,
        number_separator: this.values.number_separator,
        number_negative: this.values.number_negative,
      }
    },
  },
  watch: {
    'values.number_negative': {
      handler(newVal) {
        if (!newVal && this.values.number_default < 0) {
          this.values.number_default = '0'
          this.formattedDefaultValue = '0'
        }
      },
      immediate: true,
    },
    values: {
      handler() {
        this.updateFormattedValueIfNotFocussed()
      },
      deep: true,
    },
  },
  validations() {
    return {
      values: {
        number_decimal_places: { required },
        number_prefix: { maxLength: maxLength(10) },
        number_suffix: { maxLength: maxLength(10) },
        number_separator: {},
        number_negative: {},
        number_default: {},
      },
    }
  },
  created() {
    this.updateFormattedValue(this.field, this.values.number_default)
  },
  methods: {
    onDefaultValueFocus() {
      this.focused = true
      this.updateFormattedValue(this.field, this.values.number_default)
    },
    onDefaultValueBlur() {
      this.focused = false
      const parsedValue = this.parseNumberValue(
        this.field,
        this.formattedDefaultValue
      )
      if (!this.values.number_negative && parsedValue < 0) {
        this.values.number_default = '0'
        this.formattedDefaultValue = '0'
        return
      }
      this.values.number_default = parsedValue === null ? '' : parsedValue
      this.updateFormattedValue(this.field, this.values.number_default)
    },
    updateFormattedValueIfNotFocussed() {
      if (!this.focused) {
        this.updateFormattedValue(this.field, this.values.number_default)
      }
    },
    updateFormattedValue(field, value) {
      const numberValue = new BigNumber(value)
      if (numberValue.isNaN()) {
        this.formattedDefaultValue = ''
        return
      }
      this.formattedDefaultValue = this.formatNumberValue(field, numberValue)
    },
  },
}
</script>
