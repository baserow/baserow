<template>
  <form @submit.prevent>
    <Alert v-if="!values.integration_id" type="info-neutral">
      <p>{{ $t('slackWriteMessageServiceForm.alertMessage') }}</p>
    </Alert>
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
      :error-message="getFirstErrorMessage('channel')"
      required
      small-label
    >
      <FormInput
        v-model="v$.values.channel.$model"
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
import { maxLength, helpers } from '@vuelidate/validators'
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
        text: {},
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
        channel: {
          maxLength: maxLength(75),
          noPrefix: helpers.withMessage(
            this.$t('slackWriteMessageServiceForm.channelNoPrefix'),
            (value) => !value || !value.startsWith('#')
          ),
        },
      },
    }
  },
}
</script>
