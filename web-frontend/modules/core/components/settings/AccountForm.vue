<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      :label="$t('accountForm.nameLabel')"
      required
      :error="fieldHasErrors('first_name')"
      class="margin-bottom-2"
    >
      <FormInput
        ref="first_name"
        v-model="v$.values.first_name.$model"
        size="large"
        :error="fieldHasErrors('first_name')"
        @blur="v$.values.first_name.$touch"
      ></FormInput>

      <template #error>
        {{ v$.values.first_name.$errors[0]?.$message }}
      </template>
    </FormGroup>

    <FormGroup :label="$t('accountForm.languageLabel')" small-label required>
      <Dropdown
        v-model="v$.values.language.$model"
        :show-search="false"
        size="large"
      >
        <DropdownItem
          v-for="locale in $i18n.locales"
          :key="locale.code"
          :name="locale.name"
          :value="locale.code"
        ></DropdownItem>
      </Dropdown>
    </FormGroup>

    <slot></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, maxLength, minLength, helpers } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'AccountForm',
  mixins: [form],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['first_name', 'language'],
      values: {
        first_name: '',
        language: '',
      },
    }
  },

  validations() {
    return {
      values: {
        language: {},
        first_name: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          minLength: helpers.withMessage(
            this.$t('error.minMaxLength', {
              max: 150,
              min: 2,
            }),
            minLength(2)
          ),
          maxLength: helpers.withMessage(
            this.$t('error.minMaxLength', {
              max: 150,
              min: 2,
            }),
            maxLength(150)
          ),
        },
      },
    }
  },
}
</script>
