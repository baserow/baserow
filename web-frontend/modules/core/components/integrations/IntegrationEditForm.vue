<template>
  <form ref="form" @submit.prevent="submit">
    <FormGroup
      required
      class="margin-bottom-2"
      :error-message="
        v$.values.name.$dirty && !v$.values.name.required
          ? $t('error.requiredField')
          : !v$.values.name.maxLength
          ? $t('error.maxLength', { max: 255 })
          : ''
      "
    >
      <FormInput
        v-model="values.name"
        required
        :label="$t('integrationEditForm.name')"
        :placeholder="$t('integrationEditForm.namePlaceholder')"
        @blur="v$.values.name.$touch()"
      />
    </FormGroup>

    <component
      :is="integrationType.formComponent"
      :application="application"
      :default-values="defaultValues"
    />
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { required, maxLength } from '@vuelidate/validators'

export default {
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
    integrationType: {
      type: Object,
      required: true,
    },
  },
  data() {
    return { values: { name: '' }, allowedValues: ['name'] }
  },
  validations() {
    return {
      values: {
        name: {
          required,
          maxLength: maxLength(255),
        },
      },
    }
  },
}
</script>
