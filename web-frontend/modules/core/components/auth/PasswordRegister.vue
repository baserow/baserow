<template>
  <div>
    <Alert v-if="invitation !== null" type="info-primary">
      <template #title>{{ $t('invitationTitle') }}</template>
      <i18n path="invitationMessage" tag="p">
        <template #invitedBy>
          <strong>{{ invitation.invited_by }}</strong>
        </template>
        <template #workspace>
          <strong>{{ invitation.workspace }}</strong>
        </template>
      </i18n>
    </Alert>
    <Error :error="error"></Error>
    <form @submit.prevent="register">
      <FormGroup
        small-label
        :label="$t('field.emailAddress')"
        :error="v$.account.email.$error"
        required
        class="mb-24"
      >
        <FormInput
          v-if="invitation !== null"
          ref="email"
          v-model="account.email"
          type="email"
          disabled
          :placeholder="$t('signup.emailPlaceholder')"
        ></FormInput>

        <FormInput
          v-else
          ref="email"
          v-model="account.email"
          size="large"
          type="text"
          autocomplete="username"
          :placeholder="$t('signup.emailPlaceholder')"
          :error="v$.account.email.$error"
          @blur="v$.account.email.$touch"
        />

        <template #error>
          <i class="iconoir-warning-triangle"></i>
          {{ $t('error.invalidEmail') }}
        </template>
      </FormGroup>

      <FormGroup
        small-label
        :label="$t('field.name')"
        :error="v$.account.name.$error"
        required
        class="mb-24"
      >
        <FormInput
          ref="name"
          v-model="account.name"
          :error="v$.account.name.$error"
          type="text"
          size="large"
          :placeholder="$t('signup.namePlaceholder')"
          @blur="v$.account.name.$touch"
        >
        </FormInput>

        <template #error>
          <i class="iconoir-warning-triangle"></i>
          {{ $t('error.minMaxLength', { min: 2, max: 150 }) }}
        </template>
      </FormGroup>

      <FormGroup
        small-label
        :label="$t('field.password')"
        required
        class="mb-24"
      >
        <PasswordInput
          v-model="account.password"
          :validation-state="v$.account.password"
          :placeholder="$t('signup.passwordPlaceholder')"
          :error-placeholder-class="'auth__control-error'"
          :show-error-icon="true"
        />
      </FormGroup>

      <component
        :is="component"
        v-for="(component, index) in registerComponents"
        :ref="`register-component-${index}`"
        :key="index"
        @updated-account="updatedAccount"
      ></component>
      <div class="auth__action mt-32 mb-32">
        <Button
          type="primary"
          size="large"
          :loading="loading"
          full-width
          :disabled="loading"
        >
          {{ $t('action.getStarted') }}
        </Button>
      </div>
      <div>
        <slot></slot>
      </div>
    </form>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { email, maxLength, minLength, required } from '@vuelidate/validators'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import error from '@baserow/modules/core/mixins/error'
import PasswordInput from '@baserow/modules/core/components/helpers/PasswordInput'
import { passwordValidation } from '@baserow/modules/core/validators'

export default {
  name: 'PasswordRegister',
  components: { PasswordInput },
  mixins: [error],
  props: {
    invitation: {
      required: false,
      validator: (prop) => typeof prop === 'object' || prop === null,
      default: null,
    },
    template: {
      required: false,
      validator: (prop) => typeof prop === 'object' || prop === null,
      default: null,
    },
  },
  setup() {
    const values = reactive({
      account: {
        email: '',
        password: '',
        name: '',
      },
    })

    const rules = computed(() => ({
      account: {
        email: { required, email },
        name: {
          required,
          minLength: minLength(2),
          maxLength: maxLength(150),
        },
        password: passwordValidation,
      },
    }))

    return {
      v$: useVuelidate(rules, values, { $lazy: true }),
      account: values.account,
    }
  },
  data() {
    return {
      loading: false,
    }
  },
  computed: {
    registerComponents() {
      return Object.values(this.$registry.getAll('plugin'))
        .map((plugin) => plugin.getRegisterComponent())
        .filter((component) => component !== null)
    },
  },
  beforeMount() {
    if (this.invitation !== null) {
      this.account.email = this.invitation.email
    }
  },
  methods: {
    async register() {
      this.v$.$touch()
      let registerComponentsValid = true

      for (let i = 0; i < this.registerComponents.length; i++) {
        const ref = this.$refs[`register-component-${i}`][0]
        if (
          Object.prototype.hasOwnProperty.call(ref, 'isValid') &&
          !ref.isValid(this.account)
        ) {
          registerComponentsValid = false
        }
      }

      if (this.v$.$invalid || !registerComponentsValid) {
        return
      }

      this.loading = true
      this.hideError()

      try {
        const values = {
          name: this.account.name,
          email: this.account.email,
          password: this.account.password,
          language: this.$i18n.locale,
        }

        // If there is a valid invitation we can add the workspace invitation token to the
        // action parameters so that it can be passed along when signing up. That makes
        // the user accept the workspace invitation without creating a new workspace for the
        // user.
        if (this.invitation !== null) {
          values.workspaceInvitationToken =
            this.$route.query.workspaceInvitationToken
        }

        // If a template is provided, we can add that id to the parameters so that the
        // template will be installed right while creating the account. This is going
        // to done instead of the default example template.
        if (this.template !== null) {
          values.templateId = this.template.id
        }

        await this.$store.dispatch('auth/register', values)
        Object.values(this.$registry.getAll('plugin')).forEach((plugin) => {
          plugin.userCreated(this.account, this)
        })

        this.$emit('success', { email: values.email })
      } catch (error) {
        this.loading = false
        this.handleError(error, 'signup', {
          ERROR_EMAIL_ALREADY_EXISTS: new ResponseErrorMessage(
            this.$t('error.alreadyExistsTitle'),
            this.$t('error.alreadyExistsMessage')
          ),
          ERROR_DEACTIVATED_USER: new ResponseErrorMessage(
            this.$t('error.disabledAccountTitle'),
            this.$t('error.disabledAccountMessage')
          ),
        })
      }
    },
    updatedAccount({ key, value }) {
      this.$set(this.account, key, value)
    },
  },
}
</script>
