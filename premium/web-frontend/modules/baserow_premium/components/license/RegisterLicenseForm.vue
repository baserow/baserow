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
        v-model="v$.values.license.$model"
        :error="fieldHasErrors('license')"
        :rows="6"
        @blur="v$.values.license.$touch()"
      />

      <template #error>
        {{ v$.values.license.$errors[0]?.$message }}
      </template>
    </FormGroup>

    <slot></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'RegisterLicenseForm',
  mixins: [form],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      values: {
        license: '',
      },
    }
  },

  mounted() {
    this.$refs.license.focus()
  },
  validations() {
    return {
      values: {
        license: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
      },
    }
  },
}
</script>
