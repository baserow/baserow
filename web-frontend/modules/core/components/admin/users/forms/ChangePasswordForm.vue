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
        :validation-state="v$.values.password"
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
        @blur="v$.values.passwordConfirm.$touch()"
      ></FormInput>

      <template #error>
        {{ $t('changePasswordForm.error.doesntMatch') }}
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
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { sameAs } from '@vuelidate/validators'
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
  setup() {
    const values = reactive({
      values: {
        password: '',
        passwordConfirm: '',
      },
    })

    const rules = computed(() => ({
      values: {
        passwordConfirm: {
          sameAsPassword: sameAs(values.values.password),
        },
        password: passwordValidation,
      },
    }))

    return {
      values: values.values,
      v$: useVuelidate(rules, values, { $lazy: true }),
    }
  },
  data() {
    return {
      allowedValues: ['password', 'passwordConfirm'],
    }
  },
}
</script>
