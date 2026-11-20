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
      v-bind="
        integrationType.createsItself
          ? { integrationName: values.name, serviceTypes, integrationType }
          : {}
      "
      @created="$emit('created', $event)"
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
    /**
     * The service types the integration is used for, so a form that connects
     * an account asks for what they need.
     */
    serviceTypes: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  emits: ['created'],
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
