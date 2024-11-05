<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      required
      :label="$t('registerLicenseForm.licenseKey')"
      :error="fieldHasErrors('license')"
    >
      <FormTextarea
        ref="license"
        v-model="values.license"
        :error="fieldHasErrors('license')"
        :rows="6"
        @blur="v$.values.license.$touch()"
      />

      <template #error>
        {{ $t('error.requiredField') }}
      </template>
    </FormGroup>

    <slot></slot>
  </form>
</template>

<script>
import { required } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'RegisterLicenseForm',
  mixins: [form],
  data() {
    return {
      values: {
        license: '',
      },
    }
  },
  validations: {
    values: {
      license: { required },
    },
  },
  mounted() {
    this.$refs.license.focus()
  },
}
</script>
