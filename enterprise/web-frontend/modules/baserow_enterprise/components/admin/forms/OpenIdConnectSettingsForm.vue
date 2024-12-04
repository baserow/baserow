<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      required
      :label="$t('oauthSettingsForm.providerName')"
      :error="v$.name.$error"
      class="margin-bottom-2"
    >
      <FormInput
        ref="name"
        v-model="v$.name.$model"
        size="large"
        :error="v$.name.$error"
        :placeholder="$t('oauthSettingsForm.providerNamePlaceholder')"
        @blur="v$.name.$touch"
      ></FormInput>

      <template #error v-if="v$.name.required.$invalid">
        {{ $t('error.requiredField') }}</template
      >
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('oauthSettingsForm.baseUrl')"
      :error="v$.base_url.required.$invalid || !!serverErrors.baseUrl"
      class="margin-bottom-2"
      required
    >
      <FormInput
        ref="base_url"
        v-model="v$.base_url.$model"
        size="large"
        :error="v$.base_url.required.$invalid || !!serverErrors.baseUrl"
        :placeholder="$t('oauthSettingsForm.baseUrlPlaceholder')"
        @blur="v$.base_url.$touch"
      ></FormInput>

      <template #error>
        <div v-if="v$.base_url.required.$invalid">
          {{ $t('error.requiredField') }}
        </div>
        <div v-else-if="v$.base_url.url.$invalid">
          {{ $t('oauthSettingsForm.invalidBaseUrl') }}
        </div>
        <div v-else-if="!!serverErrors.baseUrl">
          {{ $t('oauthSettingsForm.invalidBaseUrl') }}
        </div>
      </template>
    </FormGroup>

    <FormGroup
      :error="v$.client_id.$error"
      small-label
      :label="$t('oauthSettingsForm.clientId')"
      required
      class="margin-bottom-2"
    >
      <FormInput
        ref="client_id"
        v-model="v$.client_id.$model"
        size="large"
        :error="v$.client_id.$error"
        :placeholder="$t('oauthSettingsForm.clientIdPlaceholder')"
        @blur="v$.client_id.$touch"
      ></FormInput>

      <template v-if="v$.client_id.required" #error>
        {{ $t('error.requiredField') }}
      </template>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('oauthSettingsForm.secret')"
      :error="v$.secret.$error"
      class="margin-bottom-2"
      required
    >
      <FormInput
        ref="secret"
        v-model="v$.secret.$model"
        size="large"
        :error="v$.secret.$error"
        :placeholder="$t('oauthSettingsForm.secretPlaceholder')"
        @blur="v$.secret.$touch"
      ></FormInput>

      <template #error>
        <span v-if="v$.secret.required.$invalid">
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
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { required, url } from '@vuelidate/validators'
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
      values: null,
      v$: null,
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
  created() {
    const values = reactive({
      name: '',
      base_url: '',
      client_id: '',
      secret: '',
    })

    const rules = computed(() => ({
      name: { required },
      base_url: { required, url },
      client_id: { required },
      secret: { required },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
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
      this.v$.$touch()
      if (this.v$.$invalid) {
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
}
</script>
