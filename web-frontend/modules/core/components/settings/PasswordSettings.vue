<template>
  <div>
    <h2 class="box__title">{{ $t('passwordSettings.title') }}</h2>
    <Error :error="error"></Error>
    <Alert v-if="success" type="success">
      <template #title>{{ $t('passwordSettings.changedTitle') }}</template>
      <p>{{ $t('passwordSettings.changedDescription') }}</p>
    </Alert>
    <form v-if="!success" @submit.prevent="changePassword">
      <FormGroup
        :label="$t('passwordSettings.oldPasswordLabel')"
        small-label
        required
        :error="v$.oldPassword.$error"
        class="margin-bottom-2"
      >
        <FormInput
          v-model="v$.oldPassword.$model"
          :error="v$.oldPassword.$error"
          type="password"
          size="large"
          @blur="v$.oldPassword.$touch"
        ></FormInput>
        <template #error>
          {{ $t('passwordSettings.oldPasswordRequiredError') }}</template
        >
      </FormGroup>

      <PasswordInput
        v-model="v$.newPassword.$model"
        :validation-state="v$.newPassword"
        :label="$t('passwordSettings.newPasswordLabel')"
        class="margin-bottom-2"
      ></PasswordInput>

      <FormGroup
        :error="v$.passwordConfirm.$error"
        :label="$t('passwordSettings.repeatNewPasswordLabel')"
        required
        small-label
        class="margin-bottom-2"
      >
        <FormInput
          v-model="v$.passwordConfirm.$model"
          :error="v$.passwordConfirm.$error"
          type="password"
          size="large"
          @blur="v$.passwordConfirm.$touch"
        >
        </FormInput>

        <template #error>
          {{ $t('passwordSettings.repeatNewPasswordMatchError') }}</template
        >
      </FormGroup>

      <div class="actions actions--right">
        <Button
          type="primary"
          size="large"
          :loading="loading"
          :disabled="loading"
          icon="iconoir-edit-pencil"
        >
          {{ $t('passwordSettings.submitButton') }}
        </Button>
      </div>
    </form>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { sameAs, required } from '@vuelidate/validators'

import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import error from '@baserow/modules/core/mixins/error'
import AuthService from '@baserow/modules/core/services/auth'
import PasswordInput from '@baserow/modules/core/components/helpers/PasswordInput'
import { passwordValidation } from '@baserow/modules/core/validators'

export default {
  components: { PasswordInput },
  mixins: [error],
  data() {
    return {
      values: null,
      v$: null,
      loading: false,
      success: false,
    }
  },
  created() {
    const values = reactive({
      oldPassword: '',
      newPassword: '',
      passwordConfirm: '',
    })

    const rules = computed(() => ({
      passwordConfirm: {
        sameAsPassword: sameAs(values.newPassword),
      },
      newPassword: passwordValidation,
      oldPassword: { required },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  methods: {
    async changePassword() {
      this.v$.$touch()

      if (this.v$.$invalid) {
        return
      }

      this.loading = true
      this.hideError()

      try {
        await AuthService(this.$client).changePassword(
          this.values.oldPassword,
          this.values.newPassword
        )
        // Changing the password invalidates all the refresh and access token, so we
        // have to log in again. This can be done with the new password we still have
        // in memory.
        await this.$store.dispatch('auth/login', {
          email: this.$store.getters['auth/getUsername'],
          password: this.values.newPassword,
        })
        this.success = true
        this.loading = false
      } catch (error) {
        this.loading = false
        this.handleError(error, 'changePassword', {
          ERROR_INVALID_OLD_PASSWORD: new ResponseErrorMessage(
            this.$t('passwordSettings.errorInvalidOldPasswordTitle'),
            this.$t('passwordSettings.errorInvalidOldPasswordMessage')
          ),
        })
      }
    },
  },
}
</script>
