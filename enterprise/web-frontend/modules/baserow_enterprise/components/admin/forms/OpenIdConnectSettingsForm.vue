<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      required
      :label="$t('oauthSettingsForm.providerName')"
      :error="fieldHasErrors('name')"
      class="margin-bottom-2"
    >
      <FormInput
        ref="name"
        v-model="values.name"
        size="large"
        :error="fieldHasErrors('name')"
        :placeholder="$t('oauthSettingsForm.providerNamePlaceholder')"
        @blur="$v.values.name.$touch()"
      ></FormInput>

      <template v-if="$v.values.name.$dirty && !$v.values.name.required" #error>
        {{ $t('error.requiredField') }}</template
      >
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('oauthSettingsForm.baseUrl')"
      :error="fieldHasErrors('base_url') || !!serverErrors.baseUrl"
      class="margin-bottom-2"
      required
    >
      <FormInput
        ref="base_url"
        v-model="values.base_url"
        size="large"
        :error="fieldHasErrors('base_url') || !!serverErrors.baseUrl"
        :placeholder="$t('oauthSettingsForm.baseUrlPlaceholder')"
        @blur="$v.values.base_url.$touch()"
      ></FormInput>

      <template #error>
        <div v-if="$v.values.base_url.$dirty && !$v.values.base_url.required">
          {{ $t('error.requiredField') }}
        </div>
        <div v-else-if="$v.values.base_url.$dirty && !$v.values.base_url.url">
          {{ $t('oauthSettingsForm.invalidBaseUrl') }}
        </div>
        <div v-else-if="!!serverErrors.baseUrl">
          {{ $t('oauthSettingsForm.invalidBaseUrl') }}
        </div>
      </template>
    </FormGroup>

    <FormGroup
      :error="fieldHasErrors('client_id')"
      small-label
      :label="$t('oauthSettingsForm.clientId')"
      required
      class="margin-bottom-2"
    >
      <FormInput
        ref="client_id"
        v-model="values.client_id"
        size="large"
        :error="fieldHasErrors('client_id')"
        :placeholder="$t('oauthSettingsForm.clientIdPlaceholder')"
        @blur="$v.values.client_id.$touch()"
      ></FormInput>

      <template
        v-if="$v.values.client_id.$dirty && !$v.values.client_id.required"
        #error
      >
        {{ $t('error.requiredField') }}
      </template>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('oauthSettingsForm.secret')"
      :error="fieldHasErrors('secret')"
      class="margin-bottom-2"
      required
    >
      <FormInput
        ref="secret"
        v-model="values.secret"
        size="large"
        :error="fieldHasErrors('secret')"
        :placeholder="$t('oauthSettingsForm.secretPlaceholder')"
        @blur="$v.values.secret.$touch()"
      ></FormInput>

      <template #error>
        <span v-if="$v.values.secret.$dirty && !$v.values.secret.required">
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('oauthSettingsForm.callbackUrl')"
      required
    >
      <code>{{ callbackUrl }}</code>
    </FormGroup>
    <slot></slot>
  </form>
</template>

<script>
import { required, url } from 'vuelidate/lib/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'OpenIdConnectSettingsForm',
  mixins: [form],
  props: {
    authProvider: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    serverErrors: {
      type: Object,
      required: false,
      default: () => ({}),
    },
  },
  data() {
    return {
      allowedValues: ['name', 'base_url', 'client_id', 'secret'],
      values: {
        name: '',
        base_url: '',
        client_id: '',
        secret: '',
      },
    }
  },
  computed: {
    callbackUrl() {
      if (!this.authProvider.id) {
        const nextProviderId =
          this.$store.getters['authProviderAdmin/getNextProviderId']
        return `${this.$config.PUBLIC_BACKEND_URL}/api/sso/oauth2/callback/${nextProviderId}/`
      }
      return `${this.$config.PUBLIC_BACKEND_URL}/api/sso/oauth2/callback/${this.authProvider.id}/`
    },
  },
  methods: {
    getDefaultValues() {
      return {
        name: this.authProvider.name || '',
        base_url: this.authProvider.base_url || '',
        client_id: this.authProvider.client_id || '',
        secret: this.authProvider.secret || '',
      }
    },
    submit() {
      this.$v.$touch()
      if (this.$v.$invalid) {
        return
      }
      this.$emit('submit', this.values)
    },
    handleServerError(error) {
      if (error.handler.code === 'ERROR_INVALID_PROVIDER_URL') {
        this.serverErrors.baseUrl = error.handler.detail
        return true
      }

      if (error.handler.code !== 'ERROR_REQUEST_BODY_VALIDATION') return false

      for (const [key, value] of Object.entries(error.handler.detail || {})) {
        this.serverErrors[key] = value
      }
      return true
    },
  },
  validations() {
    return {
      values: {
        name: { required },
        base_url: { required, url },
        client_id: { required },
        secret: { required },
      },
    }
  },
}
</script>
