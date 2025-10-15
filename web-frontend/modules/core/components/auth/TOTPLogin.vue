<template>
  <div>
    <svg
      class="totp-login__logo"
      width="22"
      height="22"
      viewBox="0 0 22 22"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g clip-path="url(#clip0_14_3878)">
        <path
          d="M1.18175 22H12.536C13.1892 22 13.7188 21.4705 13.7188 20.8173V17.7433C13.7188 17.0901 13.1892 16.5606 12.536 16.5606H1.18175C0.528555 16.5606 -0.00096035 17.0901 -0.00096035 17.7433V20.8173C-0.00096035 21.4705 0.528555 22 1.18175 22Z"
          fill="#4D68C4"
        />
        <path
          d="M20.8173 13.7197L1.18272 13.7197C1.0274 13.7197 0.873608 13.6891 0.730114 13.6297C0.58662 13.5703 0.456238 13.4831 0.346413 13.3733C0.236586 13.2635 0.149467 13.1331 0.0900288 12.9896C0.030592 12.8461 0 12.6923 0 12.537V9.46303C0 9.30771 0.030592 9.15391 0.0900288 9.01042C0.149467 8.86693 0.236586 8.73654 0.346413 8.62672C0.456238 8.51689 0.58662 8.42977 0.730114 8.37034C0.873608 8.3109 1.0274 8.28031 1.18272 8.28031L20.8173 8.28031C20.9726 8.28031 21.1264 8.3109 21.2699 8.37034C21.4134 8.42977 21.5438 8.51689 21.6536 8.62671C21.7634 8.73654 21.8505 8.86692 21.91 9.01041C21.9694 9.1539 22 9.3077 22 9.46301V12.537C22 12.6923 21.9694 12.8461 21.91 12.9896C21.8505 13.1331 21.7634 13.2635 21.6536 13.3733C21.5438 13.4831 21.4134 13.5703 21.2699 13.6297C21.1264 13.6891 20.9726 13.7197 20.8173 13.7197Z"
          fill="#5190EF"
        />
        <path
          d="M9.46301 5.43939L20.8173 5.43939C21.4705 5.43939 22 4.90987 22 4.25667V1.1827C22 0.529497 21.4705 -2.52724e-05 20.8173 -2.52724e-05L9.46301 -2.52724e-05C8.80981 -2.52724e-05 8.28029 0.529497 8.28029 1.1827V4.25667C8.28029 4.90987 8.80981 5.43939 9.46301 5.43939Z"
          fill="#2BC3F1"
        />
        <path
          d="M17.7433 22H20.8173C21.4705 22 22 21.4705 22 20.8173V17.7433C22 17.0901 21.4705 16.5606 20.8173 16.5606H17.7433C17.0901 16.5606 16.5606 17.0901 16.5606 17.7433V20.8173C16.5606 21.4705 17.0901 22 17.7433 22Z"
          fill="#4D68C4"
        />
        <path
          d="M4.2567 0H1.18272C0.529522 0 0 0.529522 0 1.18272V4.2567C0 4.9099 0.529522 5.43942 1.18272 5.43942H4.2567C4.90989 5.43942 5.43942 4.9099 5.43942 4.2567V1.18272C5.43942 0.529522 4.90989 0 4.2567 0Z"
          fill="#2BC3F1"
        />
      </g>
      <defs>
        <clipPath id="clip0_14_3878">
          <rect width="22" height="22" fill="white" />
        </clipPath>
      </defs>
    </svg>
    <div v-if="enterBackupCode">
      <div class="totp-login__title">Enter backup code</div>
      <div class="totp-login__description">
        Log in with your single-use backup code.
      </div>
      <FormGroup
        small-label
        :label="'Backup code'"
        :error="fieldHasErrors('values.backupCode')"
        class="margin-bottom-2"
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
      <Button
        class="totp-login__submit"
        type="primary"
        size="large"
        @click="verifyBackupCode"
        >Authenticate</Button
      >
      <div>
        <ButtonText @click="enterBackupCode = false">Go back</ButtonText>
      </div>
    </div>
    <div v-else>
      <div class="totp-login__title">Two-factor authentication</div>
      <div class="totp-login__description">
        Enter the code from your authenticator app.
      </div>
      <AuthCodeInput class="totp-login__code" @all-filled="verify" />
      <Button
        class="totp-login__submit"
        type="primary"
        size="large"
        @click="verify"
        >Verify</Button
      >
      <div>
        <ButtonText @click="enterBackupCode = true">Use backup code</ButtonText>
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
    }
  },
  methods: {
    async verify(code) {
      try {
        const { data } = await TwoFactorAuthService(this.$client).verify(
          'totp',
          this.email,
          { code }
        )
        console.log({ data })
        this.$store.dispatch('auth/loginWithData', { data })
        this.$emit('success')
        // const title = 'Successfully enabled two-factor authentication'
        // this.$store.dispatch('toast/success', { title })
        // this.$emit('verified', data.backup_codes)
      } catch (error) {
        // TODO: diff type of error?
        const title = 'Verification failed' // this.$t('generalSettings.cantUpdateApplicationTitle')
        this.$store.dispatch('toast/error', { title })
      } finally {
        // this.loading = false
      }
    },
    async verifyBackupCode(code) {
      try {
        const { data } = await TwoFactorAuthService(this.$client).verify(
          'totp',
          this.email,
          { backupCode: this.values.backupCode }
        )
        console.log({ data })
        this.$store.dispatch('auth/loginWithData', { data })
        this.$emit('success')
        // const title = 'Successfully enabled two-factor authentication'
        // this.$store.dispatch('toast/success', { title })
        // this.$emit('verified', data.backup_codes)
      } catch (error) {
        // TODO: diff type of error?
        const title = 'Verification failed' // this.$t('generalSettings.cantUpdateApplicationTitle')
        this.$store.dispatch('toast/error', { title })
      } finally {
        // this.loading = false
      }
    },
  },
}
</script>
