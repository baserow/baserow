<template>
  <FormGroup>
    <Checkbox v-model="values.boolean_default" :disabled="defaultValueDisabled">
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
  props: {
    defaultValueDisabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      allowedValues: ['boolean_default'],
      values: {
        boolean_default: false,
      },
    }
  },
  watch: {
    'values.boolean_default'(newValue) {
      this.updateParentDefaultValue(newValue)
    },
  },
  methods: {
    isFormValid() {
      return true
    },
  },
}
</script>
