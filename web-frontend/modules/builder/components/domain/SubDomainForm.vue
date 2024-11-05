<template>
  <form @submit.prevent="submit">
    <FormGroup
      :label="$t('subDomainForm.domainNameLabel')"
      small-label
      required
      :error-message="errorMessage"
    >
      <FormInput
        v-model="domainPrefix"
        @input="serverErrors.domain_name = null"
      >
        <template #suffix> .{{ domain }} </template>
      </FormInput>
    </FormGroup>
  </form>
</template>

<script>
import { maxLength, required } from '@vuelidate/validators'
import domainForm from '@baserow/modules/builder/mixins/domainForm'

export default {
  name: 'SubDomainForm',
  mixins: [domainForm],
  data() {
    return {
      domainPrefix: '',
      values: {
        domain_name: '',
      },
    }
  },
  computed: {
    errorMessage() {
      return this.v$.values.domain_name.$dirty &&
        !this.v$.values.domain_name.required
        ? this.$t('error.requiredField')
        : this.v$.values.domain_name.$dirty &&
          !this.v$.values.domain_name.maxLength
        ? this.$t('error.maxLength', { max: 255 })
        : this.serverErrors.domain_name &&
          this.serverErrors.domain_name.code === 'invalid'
        ? this.$t('domainForm.invalidDomain')
        : this.serverErrors.domain_name &&
          this.serverErrors.domain_name.code === 'unique'
        ? this.$t('domainForm.notUniqueDomain')
        : ''
    },
  },
  watch: {
    domainPrefix(value) {
      this.values.domain_name = `${value}.${this.domain}`
    },
  },
  validations() {
    return {
      values: {
        domain_name: {
          required,
          maxLength: maxLength(255),
        },
      },
    }
  },
}
</script>
