<template>
  <form @submit.prevent="submit" @keydown.enter="submit">
    <FormGroup
      :label="$t('passwordSettings.oldPasswordLabel')"
      small-label
      required
      :error="$v.values.oldPassword.$error"
      class="margin-bottom-2"
    >
      <FormInput
        v-model="values.oldPassword"
        :error="$v.values.oldPassword.$error"
        type="password"
        size="large"
        @blur="$v.values.oldPassword.$touch()"
      ></FormInput>
      <template #error>
        {{ $t('passwordSettings.oldPasswordRequiredError') }}</template
      >
    </FormGroup>

    <PasswordInput
      v-model="values.newPassword"
      :validation-state="$v.values.newPassword"
      :label="$t('passwordSettings.newPasswordLabel')"
      class="margin-bottom-2"
    ></PasswordInput>

    <FormGroup
      :error="$v.values.passwordConfirm.$error"
      :label="$t('passwordSettings.repeatNewPasswordLabel')"
      required
      small-label
      class="margin-bottom-2"
    >
      <FormInput
        v-model="values.passwordConfirm"
        :error="$v.values.passwordConfirm.$error"
        type="password"
        size="large"
        @blur="$v.values.passwordConfirm.$touch()"
      >
      </FormInput>

      <template #error>
        {{ $t('passwordSettings.repeatNewPasswordMatchError') }}</template
      >
    </FormGroup>
  </form>
</template>

<script>
import { sameAs, required } from 'vuelidate/lib/validators'
import { passwordValidation } from '@baserow/modules/core/validators'
import form from '@baserow/modules/core/mixins/form'
import PasswordInput from '@baserow/modules/core/components/helpers/PasswordInput'

export default {
  name: 'PasswordForm',
  components: { PasswordInput },
  mixins: [form],
  data() {
    return {
      values: {
        oldPassword: '',
        newPassword: '',
        passwordConfirm: '',
      },
    }
  },
  validations: {
    values: {
      passwordConfirm: {
        sameAsPassword: sameAs('newPassword'),
      },
      newPassword: passwordValidation,
      oldPassword: { required },
    },
  },
}
</script>
