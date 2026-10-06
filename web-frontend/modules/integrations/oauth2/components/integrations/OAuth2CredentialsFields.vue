<template>
  <div>
    <FormGroup
      required
      :label="$t('oauth2Credentials.clientIdLabel')"
      small-label
      class="margin-bottom-2"
      :error-message="clientIdError"
    >
      <FormInput
        :model-value="clientId"
        :placeholder="$t('oauth2Credentials.clientIdPlaceholder')"
        @update:model-value="$emit('update:client-id', $event)"
      />
    </FormGroup>
    <FormGroup
      :required="!hasClientSecret"
      :label="$t('oauth2Credentials.clientSecretLabel')"
      small-label
      class="margin-bottom-2"
      :helper-text="
        hasClientSecret ? $t('oauth2Credentials.clientSecretConfigured') : ''
      "
      :error-message="clientSecretError"
    >
      <FormInput
        :model-value="clientSecret"
        type="password"
        autocomplete="new-password"
        :placeholder="
          hasClientSecret
            ? $t('oauth2Credentials.clientSecretKeepPlaceholder')
            : $t('oauth2Credentials.clientSecretPlaceholder')
        "
        @update:model-value="$emit('update:client-secret', $event)"
      />
    </FormGroup>
  </div>
</template>

<script>
export default {
  name: 'OAuth2CredentialsFields',
  props: {
    clientId: { type: String, required: false, default: '' },
    clientSecret: { type: String, required: false, default: null },
    hasClientSecret: { type: Boolean, required: false, default: false },
    clientIdError: { type: String, required: false, default: '' },
    clientSecretError: { type: String, required: false, default: '' },
  },
  emits: ['update:client-id', 'update:client-secret'],
}
</script>
