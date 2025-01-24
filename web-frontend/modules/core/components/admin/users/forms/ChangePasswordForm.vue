<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      required
      :label="$t('changePasswordForm.newPassword')"
      class="margin-bottom-2"
    >
      <PasswordInput
        v-model="values.password"
        :validation-state="$v.values.password"
      />
    </FormGroup>

    <FormGroup
      small-label
      required
      :label="$t('changePasswordForm.repeatPassword')"
      :error="fieldHasErrors('passwordConfirm')"
    >
      <FormInput
        v-model="values.passwordConfirm"
        :error="fieldHasErrors('passwordConfirm')"
        type="password"
        size="large"
        @blur="$v.values.passwordConfirm.$touch()"
      ></FormInput>

      <template #error>
        <span v-if="!$v.values.passwordConfirm.sameAsPassword" class="error">
          {{ $t('changePasswordForm.error.doesntMatch') }}
        </span>
      </template>
    </FormGroup>

    <div class="actions">
      <div class="align-right">
        <Button
          type="primary"
          size="large"
          :disabled="loading"
          :loading="loading"
        >
          {{ $t('changePasswordForm.changePassword') }}</Button
        >
      </div>
    </div>
  </form>
</template>

<script>
import { sameAs } from 'vuelidate/lib/validators'
import PasswordInput from '@baserow/modules/core/components/helpers/PasswordInput'
import { passwordValidation } from '@baserow/modules/core/validators'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'ChangePasswordForm',
  components: { PasswordInput },
  mixins: [form],
  props: {
    loading: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      allowedValues: ['password', 'passwordConfirm'],
      values: {
        password: '',
        passwordConfirm: '',
      },
    }
  },
  validations: {
    values: {
      passwordConfirm: {
        sameAsPassword: sameAs('password'),
      },
      password: passwordValidation,
    },
  },
}
</script>
