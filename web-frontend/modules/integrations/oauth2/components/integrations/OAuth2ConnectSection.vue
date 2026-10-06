<template>
  <div class="oauth2-connect">
    <FormGroup
      :label="$t('oauth2Connect.redirectUriLabel')"
      :helper-text="$t('oauth2Connect.redirectUriHelp', { provider })"
      small-label
      class="margin-bottom-2"
    >
      <div class="oauth2-connect__redirect">
        <code class="oauth2-connect__redirect-uri">{{ redirectUri }}</code>
        <a
          v-tooltip="$t('oauth2Connect.copy')"
          class="oauth2-connect__copy"
          @click.prevent="copyRedirectUri"
        >
          <i class="iconoir-copy"></i>
          <Copied ref="copied"></Copied>
        </a>
      </div>
    </FormGroup>
    <FormGroup
      :label="$t('oauth2Connect.connectionLabel')"
      small-label
      class="margin-bottom-2"
    >
      <div class="oauth2-connect__status">
        <template v-if="connected">
          <Badge color="green" rounded>{{
            $t('oauth2Connect.connected')
          }}</Badge>
          <span
            v-if="integration.account_email"
            class="oauth2-connect__account"
          >
            {{ integration.account_email }}
          </span>
        </template>
        <Badge v-else color="yellow" rounded>{{
          $t('oauth2Connect.notConnected')
        }}</Badge>
      </div>
      <p v-if="!saved" class="oauth2-connect__hint">
        {{ $t('oauth2Connect.saveFirst') }}
      </p>
      <p v-else-if="!hasCredentials" class="oauth2-connect__hint">
        {{ $t('oauth2Connect.credentialsFirst') }}
      </p>
      <Button
        v-else
        type="secondary"
        size="regular"
        :loading="connecting"
        :disabled="connecting"
        @click.prevent="connect"
      >
        {{
          connected
            ? $t('oauth2Connect.reconnect')
            : $t('oauth2Connect.connect', { provider })
        }}
      </Button>
      <Error :error="error"></Error>
    </FormGroup>
  </div>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import OAuth2Service from '@baserow/modules/integrations/oauth2/services/oauth2'

/**
 * The part of a Google or Microsoft integration form that connects the saved
 * integration to an account. It redirects the whole page to the provider,
 * which calls Baserow back; the backend then returns the browser here.
 */
export default {
  name: 'OAuth2ConnectSection',
  mixins: [error],
  props: {
    integration: {
      type: Object,
      required: true,
    },
    provider: {
      type: String,
      required: true,
    },
  },
  data() {
    return { connecting: false }
  },
  computed: {
    saved() {
      return Boolean(this.integration.id)
    },
    hasCredentials() {
      return Boolean(
        this.integration.client_id && this.integration.has_client_secret
      )
    },
    connected() {
      return this.integration.has_refresh_token === true
    },
    redirectUri() {
      return `${this.$config.public.publicBackendUrl}/api/integration/oauth2/callback/`
    },
  },
  methods: {
    copyRedirectUri() {
      copyToClipboard(this.redirectUri)
      this.$refs.copied.show()
    },
    async connect() {
      this.hideError()
      this.connecting = true
      try {
        const { data } = await OAuth2Service(this.$client).authorize(
          this.integration.id,
          window.location.href
        )
        window.location.href = data.authorization_url
      } catch (err) {
        this.connecting = false
        this.handleError(err)
      }
    },
  },
}
</script>
