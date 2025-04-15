<template>
  <FormGroup>
    <Checkbox v-model="values.boolean_default">
      {{ $t('fieldBooleanSubForm.defaultValue') }}
    </Checkbox>
  </FormGroup>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'

export default {
  name: 'FieldBooleanSubForm',
  mixins: [form, fieldSubForm],
  data() {
    return {
      allowedValues: ['boolean_default'],
      values: {
        boolean_default: false,
      },
    }
  },
  methods: {
    isFormValid() {
      return true
    },
  },
}
</script>
