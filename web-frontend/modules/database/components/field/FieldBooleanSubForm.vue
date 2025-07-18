<template>
  <FormGroup>
    <Checkbox v-model="values.boolean_default" :disabled="isDisabled">
      {{ $t('fieldBooleanSubForm.defaultValue') }}
    </Checkbox>
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
  computed: {
    isDisabled() {
      return this.isDefaultValueFieldDisabled(
        this.values.boolean_default,
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
