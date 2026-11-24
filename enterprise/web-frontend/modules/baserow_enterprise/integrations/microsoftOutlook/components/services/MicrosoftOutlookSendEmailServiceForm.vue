<template>
  <form @submit.prevent>
    <Alert v-if="!values.integration_id" type="info-neutral">
      <p>{{ $t('microsoftOutlookForm.alertMessage') }}</p>
    </Alert>
    <FormGroup
      :label="$t('microsoftOutlookForm.integrationLabel')"
      small-label
      required
      class="margin-bottom-2"
    >
      <IntegrationDropdown
        v-model="values.integration_id"
        :application="application"
        :integrations="integrations"
        :integration-type="integrationType"
        :service-types="[serviceType.getType()]"
      />
      <template v-if="integration?.account_email" #helper>
        {{
          $t('microsoftOutlookForm.sentFrom', {
            name: integration.account_name || integration.account_email,
            email: integration.account_email,
          })
        }}
      </template>
    </FormGroup>

    <template v-if="integration">
      <Alert v-if="needsAccess" type="warning">
        <template #title>{{
          integration.connected
            ? $t('microsoftOutlookForm.grantAccessTitle')
            : $t('microsoftOutlookForm.reconnectTitle')
        }}</template>
        <p>
          {{
            integration.connected
              ? $t('microsoftOutlookForm.grantAccessDescription')
              : $t('microsoftOutlookForm.reconnectDescription')
          }}
        </p>
        <template #actions>
          <Button
            type="secondary"
            :loading="signingIn"
            :disabled="signingIn"
            @click.prevent="grantAccess"
          >
            {{
              integration.connected
                ? $t('microsoftOutlookForm.grantAccess')
                : $t('microsoftOutlookForm.reconnect')
            }}
          </Button>
        </template>
      </Alert>
      <Alert v-if="signInError" type="error">
        <p>{{ signInError }}</p>
      </Alert>
    </template>

    <FormGroup
      :label="$t('smtpEmailForm.toEmails')"
      small-label
      required
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.to_emails"
        :placeholder="$t('smtpEmailForm.toEmailsPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      :label="$t('smtpEmailForm.ccEmails')"
      small-label
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.cc_emails"
        :placeholder="$t('smtpEmailForm.ccEmailsPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      :label="$t('smtpEmailForm.bccEmails')"
      small-label
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.bcc_emails"
        :placeholder="$t('smtpEmailForm.bccEmailsPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      :label="$t('smtpEmailForm.subject')"
      small-label
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.subject"
        :placeholder="$t('smtpEmailForm.subjectPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      :label="$t('smtpEmailForm.bodyType')"
      small-label
      class="margin-bottom-2"
    >
      <Dropdown v-model="values.body_type">
        <DropdownItem :name="$t('smtpEmailForm.bodyTypePlain')" value="plain" />
        <DropdownItem :name="$t('smtpEmailForm.bodyTypeHtml')" value="html" />
      </Dropdown>
    </FormGroup>
    <FormGroup
      :label="$t('smtpEmailForm.body')"
      small-label
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.body"
        :placeholder="$t('smtpEmailForm.bodyPlaceholder')"
        textarea
      />
      <template #helper>
        {{ $t('microsoftOutlookForm.submittedHelper') }}
      </template>
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput.vue'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown.vue'
import { MicrosoftIntegrationType } from '@baserow/modules/integrations/microsoft/integrationTypes'
import {
  OAuthSignInError,
  openOAuthSignInPopup,
  useOAuthSignIn,
} from '@baserow/modules/integrations/oauthAccount/composables/useOAuthSignIn'
import { OAUTH_ERROR_CODE } from '@baserow/modules/integrations/oauthAccount/constants'
import { oauthErrorMessage } from '@baserow/modules/integrations/oauthAccount/utils'

/**
 * Sends an email from the Outlook mailbox of a Microsoft integration's
 * account. The recipients, subject and body are formulas, as in the SMTP
 * email action.
 */
export default {
  name: 'MicrosoftOutlookSendEmailServiceForm',
  components: { IntegrationDropdown, InjectedFormulaInput },
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { oauth: useOAuthSignIn(MicrosoftIntegrationType.getType()) }
  },
  data() {
    return {
      allowedValues: [
        'integration_id',
        'to_emails',
        'cc_emails',
        'bcc_emails',
        'subject',
        'body_type',
        'body',
      ],
      values: {
        integration_id: null,
        to_emails: { formula: '', mode: 'simple' },
        cc_emails: { formula: '', mode: 'simple' },
        bcc_emails: { formula: '', mode: 'simple' },
        subject: { formula: '', mode: 'simple' },
        body_type: 'plain',
        body: { formula: '', mode: 'simple' },
      },
      signingIn: false,
      signInError: '',
    }
  },
  computed: {
    serviceType() {
      return this.$registry.get('service', 'microsoft_outlook_send_email')
    },
    integrationType() {
      return this.serviceType.integrationType
    },
    integrations() {
      return this.$store.getters['integration/getIntegrations'](
        this.application
      ).filter(({ type }) => type === this.integrationType.type)
    },
    integration() {
      return (
        this.integrations.find(({ id }) => id === this.values.integration_id) ||
        null
      )
    },
    needsAccess() {
      if (!this.integration) return false
      if (!this.integration.connected) return true
      // The integration as the store holds it, current once access is
      // granted, against what the service needs.
      return (
        this.integrationType.getMissingScopes(
          this.integration,
          this.defaultValues
        ).length > 0
      )
    },
  },
  watch: {
    'values.integration_id'(id, oldId) {
      if (oldId !== undefined && id !== oldId) {
        this.signInError = ''
      }
    },
  },
  methods: {
    async grantAccess() {
      // Opened straight from the click, before any request, or it's blocked.
      const popup = openOAuthSignInPopup(this.integrationType.getType())
      this.signingIn = true
      this.signInError = ''
      try {
        await this.oauth.signIn({
          popup,
          application: this.application,
          integration: this.integration,
          serviceTypes: [this.serviceType.getType()],
        })
      } catch (error) {
        let code = null
        if (error instanceof OAuthSignInError) {
          code = error.code
        } else if (error.handler) {
          error.handler.handled()
          code = error.handler.code
        } else {
          throw error
        }
        if (code !== OAUTH_ERROR_CODE.SIGN_IN_CANCELLED) {
          this.signInError = oauthErrorMessage(
            this.$t,
            code,
            this.integrationType.providerName
          )
        }
      } finally {
        this.signingIn = false
      }
    },
  },
}
</script>
