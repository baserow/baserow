<template>
  <form ref="form" @submit.prevent="submit">
    <FormGroup
      required
      small-label
      :label="$t('integrationEditForm.name')"
      class="margin-bottom-2"
      :error-message="getFirstErrorMessage('name')"
    >
      <FormInput
        v-model="values.name"
        required
        :placeholder="$t('integrationEditForm.namePlaceholder')"
        @blur="v$.values.name.$touch"
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
import { useVuelidate } from '@vuelidate/core'
import form from '@baserow/modules/core/mixins/form'
import { required, maxLength, helpers } from '@vuelidate/validators'

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
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return { values: { name: '' }, allowedValues: ['name'] }
  },
  validations() {
    return {
      values: {
        name: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          maxLength: helpers.withMessage(
            this.$t('error.maxLength', { max: 255 }),
            maxLength(255)
          ),
        },
      },
    }
  },
}
</script>
