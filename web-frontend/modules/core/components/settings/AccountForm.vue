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
        v-model="values.first_name"
        size="large"
        :error="fieldHasErrors('first_name')"
        @blur="$v.values.first_name.$touch()"
      ></FormInput>

      <template #error>
        <span v-if="!$v.values.first_name.required">
          {{ $t('error.requiredField') }}
        </span>
        <spam v-if="hasMinMaxError">
          {{
            $t('error.minMaxLength', {
              max: $v.values.first_name.$params.maxLength.max,
              min: $v.values.first_name.$params.minLength.min,
            })
          }}
        </spam>
      </template>
    </FormGroup>

    <FormGroup :label="$t('accountForm.languageLabel')" small-label required>
      <Dropdown v-model="values.language" :show-search="false" size="large">
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
import { required, maxLength, minLength } from 'vuelidate/lib/validators'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'AccountForm',
  mixins: [form],
  data() {
    return {
      allowedValues: ['first_name', 'language'],
      values: {
        first_name: '',
        language: '',
      },
    }
  },
  computed: {
    hasMinMaxError() {
      return (
        !this.$v.values.first_name.maxLength ||
        !this.$v.values.first_name.minLength
      )
    },
  },
  validations: {
    values: {
      first_name: {
        required,
        minLength: minLength(2),
        maxLength: maxLength(150),
      },
    },
  },
}
</script>
