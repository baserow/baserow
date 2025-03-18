<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      required
      :label="$t('customDomainForm.domainNameLabel')"
      :error-message="getFirstErrorMessage('domain_name') || serverErrorMessage"
    >
      <FormInput
        ref="domainName"
        v-model="v$.values.domain_name.$model"
        size="large"
        @input="handleInput"
        @blur="v$.values.domain_name.$touch"
      />
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, maxLength, helpers } from '@vuelidate/validators'
import domainForm from '@baserow/modules/builder/mixins/domainForm'

export default {
  name: 'CustomDomainForm',
  mixins: [domainForm],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      values: {
        domain_name: '',
      },
    }
  },
  computed: {
    serverErrorMessage() {
      return this.serverErrors.domain_name
        ? this.serverErrors.domain_name.code === 'invalid'
          ? this.$t('domainForm.invalidDomain')
          : this.serverErrors.domain_name.code === 'unique'
          ? this.$t('domainForm.notUniqueDomain')
          : ''
        : ''
    },
  },
  mounted() {
    this.$refs.domainName.focus()
  },
  methods: {
    handleInput() {
      this.serverErrors.domain_name = null
      this.v$.values.domain_name.$touch()
      this.$emit('error', this.v$.$error)
    },
  },
  validations() {
    return {
      values: {
        domain_name: {
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
