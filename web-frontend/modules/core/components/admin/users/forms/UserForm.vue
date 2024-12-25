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
        v-model="values.name"
        size="large"
        :error="fieldHasErrors('name')"
        @blur="$v.values.name.$touch()"
      >
      </FormInput>
      <template #error>{{ $t('userForm.error.invalidName') }}</template>
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
        v-model="values.username"
        size="large"
        :error="fieldHasErrors('username')"
        @blur="$v.values.username.$touch()"
      >
      </FormInput>

      <template #warning>
        <span v-show="values.username !== user.username">
          {{ $t('userForm.warning.changeEmail') }}
        </span>
      </template>

      <template #error>
        <span v-show="fieldHasErrors('username')">
          {{ $t('userForm.error.invalidEmail') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('userForm.isActive')"
      required
      class="margin-bottom-2"
    >
      <Checkbox v-model="values.is_active" :disabled="loading"></Checkbox>

      <template #warning>
        <span v-show="!values.is_active">
          {{ $t('userForm.warning.inactiveUser') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup small-label :label="$t('user.isStaff')" required>
      <Checkbox v-model="values.is_staff" :disabled="loading"></Checkbox>

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
import { email, maxLength, minLength, required } from 'vuelidate/lib/validators'

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
  validations: {
    values: {
      name: { required, minLength: minLength(2), maxLength: maxLength(150) },
      username: { required, email },
    },
  },
}
</script>
