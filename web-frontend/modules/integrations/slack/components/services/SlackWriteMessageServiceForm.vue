<template>
  <form @submit.prevent>
    <FormGroup
      :label="$t('slackWriteMessageServiceForm.integrationLabel')"
      small-label
      required
      class="margin-bottom-2"
    >
      <IntegrationDropdown
        v-model="values.integration_id"
        :application="application"
        :integrations="integrations"
        :integration-type="integrationType"
      />
    </FormGroup>
    <FormGroup
      class="margin-bottom-2"
      :label="$t('slackWriteMessageServiceForm.channelLabel')"
      required
      small-label
    >
      <FormInput
        v-model="values.channel"
        icon-left="baserow-icon-hashtag"
        :placeholder="$t('slackWriteMessageServiceForm.channelPlaceholder')"
      >
      </FormInput>
    </FormGroup>
    <FormGroup
      class="margin-bottom-2"
      :label="$t('slackWriteMessageServiceForm.messageLabel')"
      required
      small-label
    >
      <InjectedFormulaInput
        v-model="values.text"
        :placeholder="$t('slackWriteMessageServiceForm.messagePlaceholder')"
      />
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput.vue'
import { useVuelidate } from '@vuelidate/core'
import { required, maxLength } from '@vuelidate/validators'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown.vue'

import { SlackBotIntegrationType } from '@baserow/modules/integrations/slack/integrationTypes'

export default {
  name: 'SlackWriteMessageServiceForm',
  components: { IntegrationDropdown, InjectedFormulaInput },
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: ['channel', 'text', 'integration_id'],
      values: {
        channel: '',
        text: '',
        integration_id: null,
      },
    }
  },
  computed: {
    integrationType() {
      return this.$registry.get(
        'integration',
        SlackBotIntegrationType.getType()
      )
    },
    integrations() {
      const allIntegrations = this.$store.getters[
        'integration/getIntegrations'
      ](this.application)
      return allIntegrations.filter(
        (integration) => integration.type === this.integrationType.type
      )
    },
  },
  validations() {
    return {
      values: {
        channel: { required, maxLength: maxLength(100) },
        text: { required, maxLength: maxLength(4000) },
        integration_id: { required },
      },
    }
  },
}
</script>
