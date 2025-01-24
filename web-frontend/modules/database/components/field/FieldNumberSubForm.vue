<template>
  <div>
    <FormGroup
      small-label
      :error="$v.values.number_decimal_places.$error"
      :label="$t('fieldNumberSubForm.decimalPlacesLabel')"
      class="margin-bottom-2"
      required
    >
      <Dropdown
        v-model="values.number_decimal_places"
        :error="$v.values.number_decimal_places.$error"
        :fixed-items="true"
        @hide="$v.values.number_decimal_places.$touch()"
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
          v-model="values.number_prefix"
          :error="$v.values.number_prefix.$error"
          type="text"
          :placeholder="$t('fieldNumberSubForm.prefixPlaceholder')"
          @blur="$v.values.number_prefix.$touch()"
        ></FormInput>
        <FormInput
          v-model="values.number_suffix"
          :error="$v.values.number_suffix.$error"
          type="text"
          :placeholder="$t('fieldNumberSubForm.suffixPlaceholder')"
          @blur="$v.values.number_suffix.$touch()"
        ></FormInput>
      </div>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('fieldNumberSubForm.separatorLabel')"
      :class="{ 'margin-bottom-2': allowSetNumberNegative }"
    >
      <Dropdown v-model="values.number_separator" :fixed-items="true">
        <DropdownItem
          v-for="option in numberFormatOptions"
          :key="option.value"
          :name="option.name"
          :value="option.value"
        />
      </Dropdown>
    </FormGroup>

    <FormGroup>
      <Checkbox
        v-if="allowSetNumberNegative"
        v-model="values.number_negative"
        >{{ $t('fieldNumberSubForm.allowNegative') }}</Checkbox
      >
    </FormGroup>
  </div>
</template>

<script>
import { required, maxLength } from 'vuelidate/lib/validators'

import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import { NUMBER_FORMATS } from '@baserow/modules/database/utils/number'

export default {
  name: 'FieldNumberSubForm',
  mixins: [form, fieldSubForm],
  props: {
    allowSetNumberNegative: {
      type: Boolean,
      required: false,
      default: true,
    },
  },
  data() {
    let allowedValues = [
      'number_decimal_places',
      'number_prefix',
      'number_suffix',
      'number_separator',
    ]
    let values = {
      number_decimal_places: 0,
      number_separator: NUMBER_FORMATS.NO_FORMATTING.value,
      number_prefix: '',
      number_suffix: '',
    }

    if (this.allowSetNumberNegative) {
      allowedValues = [...allowedValues, 'number_negative']
      values = { ...values, number_negative: false }
    }

    return {
      allowedValues,
      values,
    }
  },
  validations: {
    values: {
      number_decimal_places: { required },
      number_prefix: { maxLength: maxLength(10), required: false },
      number_suffix: { maxLength: maxLength(10), required: false },
    },
  },

  computed: {
    numberFormatOptions() {
      return Object.entries(NUMBER_FORMATS).map(([key, format]) => ({
        name: this.$t(format.description),
        value: format.value,
      }))
    },
  },
}
</script>
