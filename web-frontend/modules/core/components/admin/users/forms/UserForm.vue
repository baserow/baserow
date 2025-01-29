<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      :label="$t('userForm.fullName')"
      required
      class="margin-bottom-2"
      :error="fieldHasErrors('name')"
    >
      <FormInput
        ref="name"
        v-model="v$.values.name.$model"
        size="large"
        :error="fieldHasErrors('name')"
      >
      </FormInput>
      <template #error>{{ v$.values.name.$errors[0]?.$message }}</template>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('userForm.email')"
      required
      class="margin-bottom-2"
      :error="fieldHasErrors('username')"
    >
      <FormInput
        ref="email"
        v-model="v$.values.username.$model"
        size="large"
        :error="fieldHasErrors('username')"
      >
      </FormInput>

      <template #warning>
        <span v-show="values.username !== user.username">
          {{ $t('userForm.warning.changeEmail') }}
        </span>
      </template>

      <template #error>
        {{ v$.values.username.$errors[0]?.$message }}
      </template>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('userForm.isActive')"
      required
      class="margin-bottom-2"
    >
      <Checkbox
        v-model="v$.values.is_active.$model"
        :disabled="loading"
      ></Checkbox>

      <template #warning>
        <span v-show="!values.is_active">
          {{ $t('userForm.warning.inactiveUser') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup small-label :label="$t('user.isStaff')" required>
      <Checkbox
        v-model="v$.values.is_staff.$model"
        :disabled="loading"
      ></Checkbox>

      <template #warning>
        <span v-show="values.is_staff">
          {{ $t('userForm.warning.userStaff') }}
        </span>
      </template>
    </FormGroup>

    <div class="actions">
      <slot></slot>
      <div class="align-right">
        <Button
          type="primary"
          size="large"
          :disabled="loading"
          :loading="loading"
        >
          {{ $t('action.save') }}</Button
        >
      </div>
    </div>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import {
  email,
  maxLength,
  minLength,
  required,
  helpers,
} from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'UserForm',
  mixins: [form],
  props: {
    user: {
      type: Object,
      required: true,
    },
    loading: {
      type: Boolean,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['username', 'name', 'is_active', 'is_staff'],
      values: {
        username: '',
        name: '',
        is_active: '',
        is_staff: '',
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
          minLength: helpers.withMessage(
            this.$t('error.minLength', { min: 2 }),
            minLength(2)
          ),
          maxLength: helpers.withMessage(
            this.$t('error.maxLength', { max: 150 }),
            maxLength(150)
          ),
        },
        username: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          email: helpers.withMessage(
            this.$t('userForm.error.invalidEmail'),
            email
          ),
        },
        is_active: {},
        is_staff: {},
      },
    }
  },
}
</script>
