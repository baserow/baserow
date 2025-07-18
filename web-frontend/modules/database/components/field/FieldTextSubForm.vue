<template>
  <FormGroup>
    <FormInput
      ref="text_default"
      v-model="values.text_default"
      type="text"
      :placeholder="$t('fieldTextSubForm.placeholder')"
      :disabled="isDisabled"
    ></FormInput>
    <div v-if="isDisabled" class="control__messages padding-top-0">
      <p
        class="control__helper-text control__helper-text--warning field-context__inner-element-width"
      >
        {{ $t('fieldForm.defaultValueDisabledByConstraint') }}
      </p>
    </div>
  </FormGroup>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'

import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'

export default {
  name: 'FieldTextSubForm',
  mixins: [form, fieldSubForm],
  data() {
    return {
      allowedValues: ['text_default'],
      values: {
        text_default: '',
      },
    }
  },
  computed: {
    isDisabled() {
      return this.isDefaultValueFieldDisabled(
        this.values.text_default,
        this.formValues
      )
    },
  },
  methods: {
    isFormValid() {
      return true
    },
  },
}
</script>
