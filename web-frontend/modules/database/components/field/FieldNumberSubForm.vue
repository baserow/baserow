<template>
  <div>
    <FormGroup
      small-label
      :error="v$.number_decimal_places.$error"
      :label="$t('fieldNumberSubForm.decimalPlacesLabel')"
      :class="{ 'margin-bottom-2': allowSetNumberNegative }"
      required
    >
      <Dropdown
        v-model="v$.number_decimal_places.$model"
        :error="v$.number_decimal_places.$error"
        :fixed-items="true"
        @hide="v$.number_decimal_places.$touch"
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
        <DropdownItem
          name="10 (1.0000000000)"
          :value="10"
        ></DropdownItem> </Dropdown
    ></FormGroup>

    <FormGroup>
      <Checkbox
        v-if="allowSetNumberNegative"
        v-model="v$.number_negative.$model"
        >{{ $t('fieldNumberSubForm.allowNegative') }}</Checkbox
      >
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { required } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'

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
    let allowedValues = ['number_decimal_places']

    if (this.allowSetNumberNegative) {
      allowedValues = [...allowedValues, 'number_negative']
    }

    return {
      allowedValues,
      values: null,
      v$: null,
    }
  },
  created() {
    const values = reactive({
      number_decimal_places: 0,
      number_negative: false,
    })

    const rules = computed(() => ({
      number_decimal_places: { required },
      number_negative: {},
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
}
</script>
