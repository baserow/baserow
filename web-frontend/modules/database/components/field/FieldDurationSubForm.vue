<template>
  <FormGroup
    required
    small-label
    :label="$t('fieldDurationSubForm.durationFormatLabel')"
  >
    <Dropdown
      v-model="v$.duration_format.$model"
      :error="v$.duration_format.$error"
      :fixed-items="true"
      @hide="v$.duration_format.$touch"
    >
      <DropdownItem
        v-for="option in durationFormatOptions"
        :key="option.value"
        :name="option.name"
        :value="option.value"
      ></DropdownItem>
    </Dropdown>
  </FormGroup>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { required } from '@vuelidate/validators'
import { DURATION_FORMATS } from '@baserow/modules/database/utils/duration'

import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'

export default {
  name: 'FieldDurationSubForm',
  mixins: [form, fieldSubForm],
  data() {
    const allowedValues = ['duration_format']

    return {
      allowedValues,
      values: null,
      v$: null,
    }
  },
  computed: {
    durationFormatOptions() {
      return Array.from(DURATION_FORMATS.entries()).map(
        ([key, formatOption]) => ({
          name: formatOption.description,
          value: key,
        })
      )
    },
  },
  created() {
    const values = reactive({
      duration_format: DURATION_FORMATS.keys().next().value,
    })

    const rules = computed(() => ({
      duration_format: { required },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
}
</script>
