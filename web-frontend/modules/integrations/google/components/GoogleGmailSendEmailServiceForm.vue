<template>
  <form @submit.prevent>
    <FormGroup
      :label="$t('smtpEmailForm.integrationDropdownLabel')"
      required
      class="margin-bottom-2"
    >
      <IntegrationDropdown
        v-if="application"
        v-model="values.integration_id"
        :application="application"
        :integrations="integrations"
        :integration-type="integrationType"
        :allow-editing="
          allowIntegrationEditing || application.type === 'database'
        "
      />
    </FormGroup>
    <template
      v-if="
        selectedIntegration &&
        (!selectedIntegration.connected ||
          !selectedIntegration.granted_scopes.includes(GMAIL_SEND_SCOPE))
      "
    >
      <p>{{ $t('googleGmail.consentRequired') }}</p>
      <GoogleConnect
        :integration="selectedIntegration"
        :application="application"
        service-type="google_gmail_send_email"
      />
    </template>
    <FormGroup
      v-for="field in fields"
      :key="field.name"
      :label="$t(field.label)"
      :required="field.name === 'to_emails'"
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values[field.name]"
        :textarea="field.name === 'body'"
      />
    </FormGroup>
    <FormGroup :label="$t('smtpEmailForm.bodyType')" class="margin-bottom-2">
      <Dropdown v-model="values.body_type">
        <DropdownItem value="plain" :name="$t('smtpEmailForm.bodyTypePlain')" />
        <DropdownItem value="html" :name="$t('smtpEmailForm.bodyTypeHtml')" />
      </Dropdown>
    </FormGroup>
  </form>
</template>
<script setup>
import { computed, reactive, toRef } from 'vue'
import { useForm } from '@baserow/modules/core/composables/useForm'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import GoogleConnect from '@baserow/modules/integrations/google/components/GoogleConnect'
import { GMAIL_SEND_SCOPE } from '@baserow/modules/integrations/google/serviceTypes'
const props = defineProps({
  defaultValues: { type: Object, default: () => ({}) },
  application: { type: Object, default: null },
  service: { type: Object, default: null },
  allowIntegrationEditing: Boolean,
})
const emit = defineEmits(['values-changed'])
const { $store, $registry } = useNuxtApp()
const fields = [
  { name: 'to_emails', label: 'smtpEmailForm.toEmails' },
  { name: 'cc_emails', label: 'smtpEmailForm.ccEmails' },
  { name: 'bcc_emails', label: 'smtpEmailForm.bccEmails' },
  { name: 'subject', label: 'smtpEmailForm.subject' },
  { name: 'body', label: 'smtpEmailForm.body' },
]
const values = reactive({
  integration_id: null,
  to_emails: {},
  cc_emails: {},
  bcc_emails: {},
  subject: {},
  body: {},
  body_type: 'plain',
})
const form = useForm({
  defaultValues: toRef(props, 'defaultValues'),
  values,
  allowedValues: [
    'integration_id',
    ...fields.map(({ name }) => name),
    'body_type',
  ],
  emit,
})
const getFormValues = form.getFormValues
defineExpose({ ...form, getFormValues })
const integrationType = $registry.get('integration', 'google')
const integrations = computed(() =>
  props.application
    ? $store.getters['integration/getIntegrations'](props.application).filter(
        ({ type }) => type === 'google'
      )
    : []
)
const selectedIntegration = computed(() =>
  integrations.value.find(({ id }) => id === values.integration_id)
)
</script>
