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
        @blur="v$.values.name.$touch"
      >
      </FormInput>

      <template #error>
        <span v-if="v$.values.name.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
        <span v-else-if="v$.values.name.minLength.$invalid">
          {{ $t('error.minLength', { min: 2 }) }}
        </span>
        <span v-else-if="v$.values.name.maxLength.$invalid">
          {{ $t('error.maxLength', { max: 150 }) }}
        </span>
      </template>
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
        @blur="v$.values.username.$touch"
      >
      </FormInput>

      <template #warning>
        <span
          v-show="
            values.username !== user.username && !v$.values.username.$invalid
          "
        >
          {{ $t('userForm.warning.changeEmail') }}
        </span>
      </template>

      <template #error>
        <span v-if="v$.values.username.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
        <span v-else-if="v$.values.username.email.$invalid">
          {{ $t('error.invalidEmail') }}
        </span>
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
import { reactive } from 'vue'
import { email, maxLength, minLength, required } from '@vuelidate/validators'

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
    const values = reactive({
      values: {
        username: '',
        name: '',
        is_active: '',
        is_staff: '',
      },
    })

    const rules = {
      values: {
        name: {
          required,
          minLength: minLength(2),
          maxLength: maxLength(150),
        },
        username: {
          required,
          email,
        },
        is_active: {},
        is_staff: {},
      },
    }

    return {
      values: values.values,
      v$: useVuelidate(rules, values, { $lazy: true }),
    }
  },
  data() {
    return {
      allowedValues: ['username', 'name', 'is_active', 'is_staff'],
    }
  },
}
</script>
