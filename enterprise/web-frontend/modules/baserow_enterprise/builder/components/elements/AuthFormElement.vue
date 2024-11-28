<template>
  <form
    v-if="hasAtLeastOneLoginOption"
    class="auth-form-element"
    :style="getStyleOverride('input')"
    @submit.prevent="onLogin"
  >
    <Error :error="error"></Error>
    <ABFormGroup
      :label="$t('authFormElement.email')"
      :error-message="
        $v.values.email.$dirty
          ? !$v.values.email.required
            ? $t('error.requiredField')
            : !$v.values.email.email
            ? $t('error.invalidEmail')
            : ''
          : ''
      "
      :autocomplete="isEditMode ? 'off' : ''"
      required
    >
      <ABInput
        v-model="values.email"
        :placeholder="$t('authFormElement.emailPlaceholder')"
        @blur="$v.values.email.$touch()"
      />
    </ABFormGroup>
    <ABFormGroup
      :label="$t('authFormElement.password')"
      :error-message="
        $v.values.password.$dirty
          ? !$v.values.password.required
            ? $t('error.requiredField')
            : ''
          : ''
      "
      required
    >
      <ABInput
        ref="passwordRef"
        v-model="values.password"
        type="password"
        :placeholder="$t('authFormElement.passwordPlaceholder')"
        @blur="$v.values.password.$touch()"
      />
    </ABFormGroup>
    <div :style="getStyleOverride('login_button')" class="auth-form__footer">
      <ABButton :disabled="$v.$error" :loading="loading" size="large">
        {{ resolvedLoginButtonLabel }}
      </ABButton>
    </div>
  </form>
  <p v-else>{{ $t('authFormElement.selectOrConfigureUserSourceFirst') }}</p>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import error from '@baserow/modules/core/mixins/error'
import element from '@baserow/modules/builder/mixins/element'
import { required, email } from 'vuelidate/lib/validators'
import { ensureString } from '@baserow/modules/core/utils/validator'
import { mapActions } from 'vuex'

export default {
  name: 'AuthFormElement',
  mixins: [element, form, error],
  inject: ['elementPage', 'builder'],
  props: {
    /**
     * @type {Object}
     * @property {number} user_source_id - The id of the user_source.
     * @property {string} login_button_label - The formula for the label of the login
     *   button
     */
    element: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
      values: { email: '', password: '' },
    }
  },
  computed: {
    selectedUserSource() {
      return this.$store.getters['userSource/getUserSourceById'](
        this.builder,
        this.element.user_source_id
      )
    },
    selectedUserSourceType() {
      if (!this.selectedUserSource) {
        return null
      }
      return this.$registry.get('userSource', this.selectedUserSource.type)
    },
    isAuthenticated() {
      return this.$store.getters['userSourceUser/isAuthenticated'](this.builder)
    },
    loginOptions() {
      if (!this.selectedUserSourceType) {
        return {}
      }
      return this.selectedUserSourceType.getLoginOptions(
        this.selectedUserSource
      )
    },
    hasAtLeastOneLoginOption() {
      return Object.keys(this.loginOptions).length > 0
    },
    resolvedLoginButtonLabel() {
      return (
        ensureString(this.resolveFormula(this.element.login_button_label)) ||
        this.$t('action.login')
      )
    },
  },
  watch: {
    userSource: {
      handler(newValue) {
        if (this.element.user_source_id) {
          const found = newValue.find(
            ({ id }) => id === this.element.user_source_id
          )
          if (!found) {
            // If the user_source has been removed we need to update the element
            this.actionForceUpdateElement({
              page: this.elementPage,
              element: this.element,
              values: { user_source_id: null },
            })
          }
        }
      },
    },
  },
  methods: {
    ...mapActions({
      actionForceUpdateElement: 'element/forceUpdate',
    }),
    async onLogin(event) {
      if (this.isAuthenticated) {
        await this.$store.dispatch('userSourceUser/logoff', {
          application: this.builder,
        })
      }

      this.$v.$touch()
      if (this.$v.$invalid) {
        this.focusOnFirstError()
        return
      }
      this.loading = true
      this.hideError()
      try {
        await this.$store.dispatch('userSourceUser/authenticate', {
          application: this.builder,
          userSource: this.selectedUserSource,
          credentials: {
            email: this.values.email,
            password: this.values.password,
          },
          setCookie: this.mode === 'public',
        })
        this.values.password = ''
        this.values.email = ''
        this.$v.$reset()
        this.fireEvent(
          this.elementType.getEventByName(this.element, 'after_login')
        )
      } catch (error) {
        if (error.handler) {
          const response = error.handler.response
          if (response && response.status === 401) {
            this.values.password = ''
            this.$v.$reset()
            this.$v.$touch()
            this.$refs.passwordRef.focus()

            if (response.data?.error === 'ERROR_INVALID_CREDENTIALS') {
              this.showError(
                this.$t('error.incorrectCredentialTitle'),
                this.$t('error.incorrectCredentialMessage')
              )
            }
          } else {
            const message = error.handler.getMessage('login')
            this.showError(message)
          }

          error.handler.handled()
        } else {
          throw error
        }
      }
      this.loading = false
    },
  },
  validations: {
    values: {
      email: { required, email },
      password: { required },
    },
  },
}
</script>
