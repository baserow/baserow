<template>
  <form @submit.prevent>
    <FormGroup
      v-if="showInstanceSmtpOption"
      :label="$t('smtpEmailForm.smtpConfigurationMode')"
      small-label
      class="margin-bottom-2"
    >
      <Checkbox v-model="values.use_instance_smtp_settings">
        {{ $t('smtpEmailForm.useInstanceSmtpSettings') }}
      </Checkbox>
    </FormGroup>

    <FormGroup
      v-if="showIntegrationSelector"
      :label="$t('smtpEmailForm.integrationDropdownLabel')"
      small-label
      required
      class="margin-bottom-2"
    >
      <IntegrationDropdown
        v-if="application"
        v-model="values.integration_id"
        :application="application"
        :integrations="integrations"
        :integration-type="integrationType"
        :allow-editing="editableFromHere"
      />
    </FormGroup>

    <FormGroup
      v-if="!sendsThroughInstance"
      small-label
      :label="$t('smtpEmailForm.fromEmail')"
      required
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.from_email"
        :placeholder="$t('smtpEmailForm.fromEmailPlaceholder')"
      />
    </FormGroup>

    <FormGroup
      v-if="!sendsThroughInstance"
      small-label
      :label="$t('smtpEmailForm.fromName')"
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.from_name"
        :placeholder="$t('smtpEmailForm.fromNamePlaceholder')"
      />
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('smtpEmailForm.toEmails')"
      required
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.to_emails"
        :placeholder="$t('smtpEmailForm.toEmailsPlaceholder')"
      />
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('smtpEmailForm.ccEmails')"
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.cc_emails"
        :placeholder="$t('smtpEmailForm.ccEmailsPlaceholder')"
      />
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('smtpEmailForm.bccEmails')"
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.bcc_emails"
        :placeholder="$t('smtpEmailForm.bccEmailsPlaceholder')"
      />
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('smtpEmailForm.subject')"
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.subject"
        :placeholder="$t('smtpEmailForm.subjectPlaceholder')"
      />
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('smtpEmailForm.bodyType')"
      class="margin-bottom-2"
    >
      <Dropdown v-model="values.body_type">
        <DropdownItem :name="$t('smtpEmailForm.bodyTypePlain')" value="plain" />
        <DropdownItem :name="$t('smtpEmailForm.bodyTypeHtml')" value="html" />
      </Dropdown>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('smtpEmailForm.body')"
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.body"
        :enabled-modes="bodyFormulaMode"
        :placeholder="$t('smtpEmailForm.bodyPlaceholder')"
        textarea
      />
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'
import Checkbox from '@baserow/modules/core/components/Checkbox'
import { SMTPIntegrationType } from '@baserow/modules/integrations/core/integrationTypes'
import { BASEROW_FORMULA_MODES } from '@baserow/modules/core/formula/constants'

export default {
  name: 'CoreSMTPEmailServiceForm',
  components: {
    Checkbox,
    InjectedFormulaInput,
    IntegrationDropdown,
  },
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: false,
      default: null,
    },
    service: {
      type: Object,
      required: false,
      default: null,
    },
    // False where the service cannot carry an integration, such as a button
    // field's actions. The instance server is then the only way to send, so
    // neither the choice nor the dropdown is worth offering.
    allowIntegration: {
      type: Boolean,
      required: false,
      default: true,
    },
    // Whether this installation can send through its own server, for a
    // caller that knows better than the saved service, such as a button
    // field's action. False offers only an integration, without changing the
    // stored choice until the user makes one. Null reads the service.
    instanceSmtpAvailable: {
      type: Boolean,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      allowedValues: [
        'integration_id',
        'use_instance_smtp_settings',
        'from_email',
        'from_name',
        'to_emails',
        'cc_emails',
        'bcc_emails',
        'subject',
        'body_type',
        'body',
      ],
      values: {
        integration_id: null,
        // Where the service cannot carry an integration the instance server is
        // the only way to send, so that is what an untouched form holds. Set
        // here rather than after mount, or the mixin's watcher would report a
        // change the user never made.
        use_instance_smtp_settings: !this.allowIntegration,
        from_email: {},
        from_name: {},
        to_emails: {},
        cc_emails: {},
        bcc_emails: {},
        subject: {},
        body_type: 'plain',
        body: {},
      },
    }
  },
  computed: {
    bodyFormulaMode() {
      return this.values.body_type !== 'html'
        ? BASEROW_FORMULA_MODES
        : ['raw', 'simple']
    },
    showInstanceSmtpOption() {
      if (this.instanceSmtpAvailable !== null) {
        return this.allowIntegration && this.instanceSmtpAvailable
      }
      return (
        this.allowIntegration &&
        Boolean(this.service?.instance_smtp_settings_enabled)
      )
    },
    showIntegrationSelector() {
      return (
        this.allowIntegration &&
        (!this.showInstanceSmtpOption || !this.sendsThroughInstance)
      )
    },
    // Where the instance is not offered, an integration is what sends, even
    // if the stored choice still names the instance.
    sendsThroughInstance() {
      if (this.instanceSmtpAvailable === false) {
        return false
      }
      return this.values.use_instance_smtp_settings
    },
    // A database has no integrations page of its own, so the dropdown is the
    // only place to edit one, as with the Slack action.
    editableFromHere() {
      return this.application?.type === 'database'
    },
    integrations() {
      if (!this.application) {
        return []
      }
      const allIntegrations = this.$store.getters[
        'integration/getIntegrations'
      ](this.application)
      return allIntegrations.filter(
        (integration) => integration.type === SMTPIntegrationType.getType()
      )
    },
    integrationType() {
      return this.$registry.get('integration', SMTPIntegrationType.getType())
    },
  },
}
</script>
