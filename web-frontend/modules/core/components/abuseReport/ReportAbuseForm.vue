<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      :label="$t('reportAbuseForm.nameLabel')"
      :error="fieldHasErrors('name')"
      required
      class="margin-bottom-2"
    >
      <FormInput
        ref="name"
        v-model="v$.values.name.$model"
        :error="fieldHasErrors('name')"
        size="large"
        @blur="v$.values.name.$touch"
      ></FormInput>
      <template #error>{{ v$.values.name.$errors[0]?.$message }}</template>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('reportAbuseForm.emailLabel')"
      :error="fieldHasErrors('email')"
      required
      class="margin-bottom-2"
    >
      <FormInput
        v-model="v$.values.email.$model"
        :error="fieldHasErrors('email')"
        size="large"
        @blur="v$.values.email.$touch"
      ></FormInput>
      <template #error>{{ v$.values.email.$errors[0]?.$message }}</template>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('reportAbuseForm.descriptionLabel')"
      :helper-text="$t('reportAbuseForm.descriptionHelper')"
      :error="fieldHasErrors('description')"
      required
      class="margin-bottom-2"
    >
      <FormTextarea
        v-model="v$.values.description.$model"
        :error="fieldHasErrors('description')"
        :rows="6"
        :placeholder="$t('reportAbuseForm.descriptionPlaceholder')"
        @blur="v$.values.description.$touch"
      ></FormTextarea>
      <template #error>{{
        v$.values.description.$errors[0]?.$message
      }}</template>
    </FormGroup>
    <slot></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import {
  required,
  email,
  minLength,
  maxLength,
  helpers,
} from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'ReportAbuseForm',
  mixins: [form],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      values: {
        name: '',
        email: '',
        description: '',
      },
    }
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
            this.$t('error.maxLength', { max: 150 }),
            maxLength(150)
          ),
        },
        email: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          email: helpers.withMessage(this.$t('error.invalidEmail'), email),
        },
        description: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          minLength: helpers.withMessage(
            this.$t('error.minLength', { min: 100 }),
            minLength(100)
          ),
          maxLength: helpers.withMessage(
            this.$t('error.maxLength', { max: 1000 }),
            maxLength(1000)
          ),
        },
      },
    }
  },
  mounted() {
    this.$refs.name.focus()
  },
}
</script>
