<template>
  <FormGroup
    required
    small-label
    :label="$t('fieldDurationSubForm.durationFormatLabel')"
  >
    <Dropdown
      v-model="values.duration_format"
      :error="$v.values.duration_format.$error"
      :fixed-items="true"
      @hide="$v.values.duration_format.$touch()"
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
import { required } from 'vuelidate/lib/validators'
import { DURATION_FORMATS } from '@baserow/modules/database/utils/duration'

import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'

export default {
  name: 'FieldDurationSubForm',
  mixins: [form, fieldSubForm],
  data() {
    const allowedValues = ['duration_format']
    const values = { duration_format: DURATION_FORMATS.keys().next().value }

    return {
      allowedValues,
      values,
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
  validations: {
    values: {
      duration_format: { required },
    },
  },
}
</script>
