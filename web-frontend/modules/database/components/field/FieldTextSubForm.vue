<template>
  <FormGroup>
    <FormInput
      ref="text_default"
      v-model="values.text_default"
      type="text"
      :placeholder="$t('fieldTextSubForm.placeholder')"
    ></FormInput>
  </FormGroup>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import childForm from '@baserow/modules/core/mixins/childForm'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'

export default {
  name: 'FieldTextSubForm',
  mixins: [form, fieldSubForm, childForm],
  data() {
    return {
      allowedValues: ['text_default'],
      values: {
        text_default: '',
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
