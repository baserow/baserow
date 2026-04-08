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
      />
    </FormGroup>

    <FormGroup
      v-if="!values.use_instance_smtp_settings"
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
      v-if="!values.use_instance_smtp_settings"
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
        use_instance_smtp_settings: false,
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
      return Boolean(this.service?.instance_smtp_settings_enabled)
    },
    showIntegrationSelector() {
      return (
        !this.showInstanceSmtpOption || !this.values.use_instance_smtp_settings
      )
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
