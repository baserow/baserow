<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      required
      :label="$t('samlSettingsForm.domain')"
      :error="fieldHasErrors('domain')"
      class="margin-bottom-2"
    >
      <img
        v-if="authProvider && authProvider.is_verified"
        class="control__label-right-icon"
        :alt="$t('samlSettingsForm.providerIsVerified')"
        :title="$t('samlSettingsForm.providerIsVerified')"
        :src="getVerifiedIcon()"
      />

      <FormInput
        ref="domain"
        v-model="values.domain"
        size="large"
        :error="fieldHasErrors('domain') || serverErrors.domain"
        :placeholder="$t('samlSettingsForm.domainPlaceholder')"
        @input="serverErrors.domain = null"
        @blur="v$.values.domain.$touch()"
      ></FormInput>

      <template #error>
        <span v-if="v$.values.domain.$dirty && !v$.values.domain.required">
          {{ $t('error.requiredField') }}
        </span>

        <span
          v-else-if="
            v$.values.domain.$dirty && !v$.values.domain.mustHaveUniqueDomain
          "
          class="error"
        >
          {{ $t('samlSettingsForm.domainAlreadyExists') }}
        </span>

        <span v-else-if="serverErrors.domain" class="error">
          {{ $t('samlSettingsForm.invalidDomain') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      small-label
      required
      :label="$t('samlSettingsForm.metadata')"
      :error="fieldHasErrors('metadata')"
      class="margin-bottom-2"
    >
      <FormTextarea
        ref="metadata"
        v-model="values.metadata"
        :rows="12"
        :error="fieldHasErrors('metadata') || serverErrors.metadata"
        :placeholder="$t('samlSettingsForm.metadataPlaceholder')"
        @input="serverErrors.metadata = null"
        @blur="v$.values.metadata.$touch()"
      ></FormTextarea>

      <template #error>
        <span v-if="v$.values.metadata.$dirty && !v$.values.metadata.required">
          {{ $t('error.requiredField') }}
        </span>
        <span v-else-if="serverErrors.metadata">
          {{ $t('samlSettingsForm.invalidMetadata') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      small-label
      required
      :label="$t('samlSettingsForm.relayStateUrl')"
      class="margin-bottom-2"
    >
      <code>{{ getRelayStateUrl() }}</code>
    </FormGroup>

    <FormGroup
      small-label
      required
      :label="$t('samlSettingsForm.acsUrl')"
      class="margin-bottom-2"
    >
      <code>{{ getAcsUrl() }}</code>
    </FormGroup>

    <slot></slot>
  </form>
</template>

<script>
import { required } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'SamlSettingsForm',
  mixins: [form],
  props: {
    authProvider: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    authProviderType: {
      type: String,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      allowedValues: ['domain', 'metadata'],
      serverErrors: {},
      values: {
        domain: '',
        metadata: '',
      },
    }
  },
  computed: {
    samlDomains() {
      const samlAuthProviders =
        this.$store.getters['authProviderAdmin/getAll'].saml?.authProviders ||
        []
      return samlAuthProviders
        .filter(
          (authProvider) => authProvider.domain !== this.authProvider.domain
        )
        .map((authProvider) => authProvider.domain)
    },
    type() {
      return this.authProviderType || this.authProvider.type
    },
  },
  methods: {
    getDefaultValues() {
      return {
        domain: this.authProvider.domain || '',
        metadata: this.authProvider.metadata || '',
      }
    },
    getRelayStateUrl() {
      return this.$store.getters['authProviderAdmin/getType'](this.type)
        .relayStateUrl
    },
    getAcsUrl() {
      return this.$store.getters['authProviderAdmin/getType'](this.type).acsUrl
    },
    getVerifiedIcon() {
      return this.$registry.get('authProvider', this.type).getVerifiedIcon()
    },
    submit() {
      this.v$.$touch()
      if (this.v$.$invalid) {
        return
      }
      this.$emit('submit', this.values)
    },
    mustHaveUniqueDomain(domain) {
      return !this.samlDomains.includes(domain.trim())
    },
    handleServerError(error) {
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
        domain: { required, mustHaveUniqueDomain: this.mustHaveUniqueDomain },
        metadata: { required },
      },
    }
  },
}
</script>
