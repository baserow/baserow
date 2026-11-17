<template>
  <form @submit.prevent="submit">
    <FormGroup
      :label="$t('subDomainForm.domainNameLabel')"
      small-label
      required
      :error-message="
        v$.domainPrefix.$errors[0]?.$message || serverErrorMessage
      "
    >
      <FormInput v-model="v$.domainPrefix.$model" @input="handleInput">
        <template #suffix> .{{ domain }} </template>
      </FormInput>
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { maxLength, required, helpers } from '@vuelidate/validators'
import domainForm from '@baserow/modules/builder/mixins/domainForm'

// Browsers resolve several Unicode characters to a dot in a domain name. The NFKC
// normalization maps them to a dot, except for the ideographic full stop.
const LABEL_SEPARATORS = ['.', '\u3002']
const containsLabelSeparator = (value) => {
  const normalized = value.normalize('NFKC')
  return LABEL_SEPARATORS.some((separator) => normalized.includes(separator))
}

export default {
  name: 'SubDomainForm',
  mixins: [domainForm],
  emits: ['error'],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      domainPrefix: '',
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
  watch: {
    domainPrefix(value) {
      this.values.domain_name = `${value}.${this.domain}`
    },
  },
  methods: {
    handleInput() {
      this.serverErrors.domain_name = null
      this.v$.domainPrefix.$touch()
      this.$emit('error', this.v$.$error)
    },
  },
  validations() {
    return {
      domainPrefix: {
        required: helpers.withMessage(this.$t('error.requiredField'), required),
        maxLength: helpers.withMessage(
          this.$t('error.maxLength', { max: 255 }),
          maxLength(255)
        ),
        noDot: helpers.withMessage(
          this.$t('subDomainForm.noDotError'),
          (value) => !helpers.req(value) || !containsLabelSeparator(value)
        ),
      },
    }
  },
}
</script>
