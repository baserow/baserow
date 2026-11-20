<template>
  <div class="oauth-account-form">
    <div v-if="configLoading" class="loading"></div>

    <Alert v-else-if="!canSignIn" type="info">
      <template #title>{{
        $t('oauthAccountForm.notConfiguredTitle', { provider })
      }}</template>
      <p>{{ $t('oauthAccountForm.notConfigured', { provider }) }}</p>
      <p v-if="redirectUri" class="oauth-account-form__redirect">
        {{ $t('oauthAccountForm.redirectUri') }}
        <code>{{ redirectUri }}</code>
      </p>
    </Alert>

    <template v-else>
      <div v-if="hasAccount" class="oauth-account-form__account">
        <img
          v-if="logo"
          class="oauth-account-form__account-logo"
          :src="logo"
          alt=""
        />
        <div class="oauth-account-form__account-body">
          <div class="oauth-account-form__account-name">
            {{ defaultValues.account_name || defaultValues.account_email }}
            <Badge :color="connected ? 'green' : 'red'" rounded>
              {{
                connected
                  ? $t('oauthAccountForm.connected')
                  : $t('oauthAccountForm.disconnected')
              }}
            </Badge>
          </div>
          <div class="oauth-account-form__account-detail">
            {{ defaultValues.account_email }}
            <slot name="account-detail" :default-values="defaultValues"></slot>
          </div>
          <div
            v-if="connectedByLabel"
            class="oauth-account-form__account-detail"
          >
            {{ connectedByLabel }}
          </div>
        </div>
      </div>
      <p v-else class="oauth-account-form__intro">
        {{ $t('oauthAccountForm.intro', { provider }) }}
      </p>

      <Alert v-if="hasAccount && !connected" type="warning">
        <p>{{ $t('oauthAccountForm.reconnectNeeded', { provider }) }}</p>
      </Alert>

      <!-- Provider extras, e.g. the fields of an OAuth client of its own. -->
      <slot
        name="extras"
        :is-edit="isEdit"
        :connected="connected"
        :busy="busy"
      ></slot>

      <div class="oauth-account-form__actions">
        <Button
          type="secondary"
          :loading="signingIn"
          :disabled="busy"
          @click.prevent="signIn"
        >
          <img
            v-if="logo"
            class="oauth-account-form__button-logo"
            :src="logo"
            alt=""
          />
          {{
            isEdit
              ? $t('oauthAccountForm.reconnect')
              : $t('oauthAccountForm.signIn', { provider })
          }}
        </Button>
        <Button v-if="signingIn" type="secondary" @click.prevent="cancelSignIn">
          {{ $t('action.cancel') }}
        </Button>
        <Button
          v-else-if="isEdit && connected"
          type="secondary"
          :loading="disconnecting"
          :disabled="busy"
          @click.prevent="disconnect"
        >
          {{ $t('oauthAccountForm.disconnect') }}
        </Button>
      </div>

      <p class="oauth-account-form__note">
        <i class="iconoir-info-empty"></i>
        {{ actsAsNote }}
      </p>
      <p
        v-if="isEdit && connected && keepsConnectionInPublishedCopies"
        class="oauth-account-form__note oauth-account-form__note--muted"
      >
        {{ $t('oauthAccountForm.publishedNote') }}
      </p>

      <Alert v-if="signInError" type="error">
        <template #title>{{
          $t('oauthAccountForm.signInFailedTitle')
        }}</template>
        <p>{{ signInError.message }}</p>
        <div
          v-if="signInError.adminConsentUrl"
          class="oauth-account-form__admin-consent"
        >
          <FormInput :model-value="signInError.adminConsentUrl" readonly />
          <Button
            type="secondary"
            icon="iconoir-copy"
            @click.prevent="copyAdminConsentUrl"
          >
            {{ $t('oauthAccountForm.copyLink') }}
          </Button>
        </div>
      </Alert>
    </template>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { copyToClipboard } from '@baserow/modules/core/utils/clipboard'
import {
  OAuthSignInError,
  openOAuthSignInPopup,
  useOAuthSignIn,
} from '@baserow/modules/integrations/oauthAccount/composables/useOAuthSignIn'
import { OAUTH_ERROR_CODE } from '@baserow/modules/integrations/oauthAccount/constants'
import { oauthErrorMessage } from '@baserow/modules/integrations/oauthAccount/utils'

/**
 * Connects an account by signing in with its provider in a popup, for every
 * integration type that extends `OAuthAccountIntegrationType`. When creating,
 * the sign-in creates the integration, so the form emits `created` instead of
 * the modal's create button doing it. A provider that needs more fields wraps
 * it and puts them in the `extras` slot.
 */
export default {
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
    /** The integration type, an `OAuthAccountIntegrationType`. */
    integrationType: {
      type: Object,
      required: true,
    },
    /** The name typed in the form around this one, for a new integration. */
    integrationName: {
      type: String,
      required: false,
      default: '',
    },
    /**
     * The service types the integration is created for. The sign-in asks for
     * the permissions they need.
     */
    serviceTypes: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  emits: ['created'],
  setup(props) {
    return { oauth: useOAuthSignIn(props.integrationType.getType()) }
  },
  data() {
    return {
      values: {},
      allowedValues: [],
      configLoading: true,
      config: null,
      redirectUri: '',
      allowAccountSwitch: true,
      keepsConnectionInPublishedCopies: true,
      signingIn: false,
      disconnecting: false,
      signInError: null,
      abortController: null,
    }
  },
  computed: {
    provider() {
      return this.integrationType.providerName
    },
    logo() {
      return this.integrationType.image
    },
    isEdit() {
      return Boolean(this.defaultValues.id)
    },
    hasAccount() {
      return (
        this.isEdit &&
        Boolean(
          this.defaultValues.account_email || this.defaultValues.account_name
        )
      )
    },
    canSignIn() {
      return this.integrationType.canSignIn(this.config, this.defaultValues)
    },
    connected() {
      return this.defaultValues.connected === true
    },
    busy() {
      return this.signingIn || this.disconnecting
    },
    actsAsNote() {
      if (!this.isEdit || !this.connected) {
        return this.$t('oauthAccountForm.actsAsNote')
      }
      return this.allowAccountSwitch
        ? this.$t('oauthAccountForm.reconnectNote')
        : this.$t('oauthAccountForm.reconnectSameAccountNote')
    },
    connectedByLabel() {
      if (!this.defaultValues.connected_by_name) return ''
      return this.$t('oauthAccountForm.connectedBy', {
        name: this.defaultValues.connected_by_name,
        date: this.formatDate(this.defaultValues.connected_at),
      })
    },
  },
  beforeUnmount() {
    this.abortController?.abort()
  },
  async mounted() {
    try {
      const { data } = await this.oauth.getConfig()
      this.config = data
      this.redirectUri = data.redirect_uri
      this.allowAccountSwitch = data.allow_account_switch !== false
      this.keepsConnectionInPublishedCopies =
        data.keep_connection_in_published_copies !== false
    } catch (error) {
      this.config = null
    } finally {
      this.configLoading = false
    }
  },
  methods: {
    formatDate(value) {
      if (!value) return ''
      return new Date(value).toLocaleDateString(this.$i18n.locale, {
        dateStyle: 'medium',
      })
    },
    async signIn() {
      // Opened straight from the click, before any request, or it's blocked.
      const popup = openOAuthSignInPopup(this.integrationType.getType())
      this.signingIn = true
      this.signInError = null
      this.abortController = new AbortController()
      try {
        const { created, integration } = await this.oauth.signIn({
          popup,
          application: this.application,
          integration: this.isEdit ? this.defaultValues : null,
          serviceTypes: this.serviceTypes,
          name: this.integrationName,
          signal: this.abortController.signal,
        })
        if (created) {
          this.$emit('created', integration)
        }
      } catch (error) {
        this.showError(error)
      } finally {
        this.signingIn = false
        this.abortController = null
      }
    },
    cancelSignIn() {
      // The popup may be cut off from this page, so its closing can't be
      // waited for: the person gives up here instead.
      this.abortController?.abort()
    },
    async disconnect() {
      this.disconnecting = true
      this.signInError = null
      try {
        await this.oauth.disconnect(this.application, this.defaultValues)
      } catch (error) {
        this.showError(error)
      } finally {
        this.disconnecting = false
      }
    },
    showError(error) {
      let code = null
      let detail = null
      if (error instanceof OAuthSignInError) {
        code = error.code
        detail = error.detail
      } else if (error.handler) {
        error.handler.handled()
        code = error.handler.code
        detail = error.handler.detail
      } else {
        throw error
      }
      if (code === OAUTH_ERROR_CODE.SIGN_IN_CANCELLED) {
        // Closing or declining the sign-in isn't an error to report.
        return
      }
      this.signInError = {
        message: oauthErrorMessage(this.$t, code, this.provider),
        adminConsentUrl:
          code === OAUTH_ERROR_CODE.ADMIN_CONSENT_REQUIRED && detail
            ? detail
            : null,
      }
    },
    copyAdminConsentUrl() {
      copyToClipboard(this.signInError.adminConsentUrl)
      this.$store.dispatch('toast/info', {
        title: this.$t('oauthAccountForm.linkCopied'),
      })
    },
  },
}
</script>
