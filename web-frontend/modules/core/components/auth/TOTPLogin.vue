<template>
  <div class="auth__wrapper">
    <div>
      <div class="auth__logo">
        <nuxt-link :to="{ name: 'index' }">
          <Logo />
        </nuxt-link>
      </div>
      <div v-if="enterBackupCode">
        <div class="auth__head auth__head-title">
          <h1>
            {{ $t('totpLogin.backupCodesTitle') }}
          </h1>
        </div>
        <p class="auth__head-text">
          {{ $t('totpLogin.backupCodesDescription') }}
        </p>
        <Alert v-if="errorTitle" type="error">
          <template #title>{{ errorTitle }}</template>
          <p>{{ errorDescription }}</p>
        </Alert>
        <FormGroup
          small-label
          :label="'Backup code'"
          :error="fieldHasErrors('values.backupCode')"
          class="mb-32"
          required
        >
          <FormInput
            ref="backup_code"
            v-model="v$.values.backupCode.$model"
            size="large"
            :error="fieldHasErrors('values.backupCode')"
            :placeholder="'XXXXX-XXXXX'"
            @blur="v$.values.backupCode.$touch"
          ></FormInput>
          <template #error>
            {{ v$.values.backupCode.$errors[0]?.$message }}
          </template>
        </FormGroup>
        <div class="mb-32">
          <Button
            class="totp-login__submit"
            type="primary"
            full-width
            size="large"
            :loading="loadingVerifyBackupCode"
            @click="verifyBackupCode"
            >{{ $t('totpLogin.authenticate') }}</Button
          >
        </div>
        <div>
          <ul class="auth__action-links">
            <li class="auth__action-link">
              <ButtonText
                type="secondary"
                tag="a"
                @click="enterBackupCode = false"
                >{{ $t('totpLogin.goBack') }}</ButtonText
              >
            </li>
          </ul>
        </div>
      </div>
      <div v-else>
        <div class="auth__head auth__head-title">
          <h1>{{ $t('totpLogin.totpTitle') }}</h1>
        </div>
        <p class="auth__head-text">
          {{ $t('totpLogin.totpDescription') }}
        </p>
        <Alert v-if="errorTitle" type="error">
          <template #title>{{ errorTitle }}</template>
          <p>{{ errorDescription }}</p>
        </Alert>
        <AuthCodeInput
          ref="authCodeInput"
          class="mb-32"
          :full-width="true"
          @all-filled="verify"
        />
        <div class="mb-32">
          <Button
            class="mb-32"
            type="primary"
            full-width
            size="large"
            :loading="loadingVerifyCode"
            @click="verify"
            >{{ $t('totpLogin.verify') }}</Button
          >
        </div>
        <div>
          <ul class="auth__action-links">
            <li class="auth__action-link">
              <ButtonText
                type="secondary"
                tag="a"
                @click="enterBackupCode = true"
                >{{ $t('totpLogin.useBackupCode') }}</ButtonText
              >
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import AuthCodeInput from '@baserow/modules/core/components/settings/twoFactorAuth/AuthCodeInput.vue'
import TwoFactorAuthService from '@baserow/modules/core/services/twoFactorAuth'
import form from '@baserow/modules/core/mixins/form'
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { required } from '@vuelidate/validators'

export default {
  name: 'TOTPLogin',
  components: { AuthCodeInput },
  mixins: [form],
  props: {
    email: {
      type: String,
      required: true,
    },
    token: {
      type: String,
      required: true,
    },
  },
  setup() {
    const values = reactive({
      values: {
        backupCode: '',
      },
    })

    const rules = computed(() => ({
      values: {
        backupCode: { required },
      },
    }))

    return {
      v$: useVuelidate(rules, values, { $lazy: true }),
      values: values.values,
    }
  },
  data() {
    return {
      enterBackupCode: false,
      loadingVerifyCode: false,
      loadingVerifyBackupCode: false,
      errorTitle: null,
      errorDescription: null,
    }
  },
  watch: {
    enterBackupCode() {
      this.errorTitle = null
      this.errorDescription = null
    },
  },
  methods: {
    async verify(code) {
      this.errorTitle = null
      this.errorDescription = null
      this.loadingVerifyCode = true
      try {
        const { data } = await TwoFactorAuthService(this.$client).verify(
          'totp',
          this.email,
          this.token,
          { code }
        )
        this.$store.dispatch('auth/loginWithData', { data })
        this.$emit('success')
      } catch (error) {
        this.loadingVerifyCode = false
        this.$refs.authCodeInput.reset()
        this.handleError(error)
      }
    },
    async verifyBackupCode(code) {
      this.errorTitle = null
      this.errorDescription = null
      this.loadingVerifyBackupCode = true
      try {
        const { data } = await TwoFactorAuthService(this.$client).verify(
          'totp',
          this.email,
          this.token,
          { backup_code: this.values.backupCode }
        )
        this.$store.dispatch('auth/loginWithData', { data })
        this.$emit('success')
      } catch (error) {
        this.loadingVerifyBackupCode = false
        this.handleError(error)
      }
    },
    handleError(error) {
      const data = error.response.data
      if (error.response.status === 429) {
        const title = this.$t('totpLogin.rateLimit')
        this.$store.dispatch('toast/error', { title })
        return
      }
      if (error.response.status !== 401) {
        return
      }
      if (
        data.detail &&
        data.detail === 'Authentication credentials were not provided.'
      ) {
        const title = this.$t('totpLogin.loginExpired')
        const description = this.$t('totpLogin.loginExpiredDescription')
        this.errorTitle = title
        this.errorDescription = description
        this.$emit('expired')
      } else {
        const title = this.$t('totpLogin.verificationFailed')
        const description = this.$t('totpLogin.verificationFailedDescription')
        this.errorTitle = title
        this.errorDescription = description
      }
    },
  },
}
</script>
