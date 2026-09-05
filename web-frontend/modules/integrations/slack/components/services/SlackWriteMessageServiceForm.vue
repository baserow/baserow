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
        :allow-editing="editableFromHere"
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

// `SlackWriteMessageService.channel` in the backend.
const CHANNEL_MAX_LENGTH = 80

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
    /**
     * A database has no integration settings page, so a bot that arrived
     * without its token can only be repaired from the picker. Everywhere else
     * has one, and a second route there would only be harder to find.
     */
    editableFromHere() {
      return this.application?.type === 'database'
    },
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
          // The column holds 80, which the serializer is pinned to. A
          // stricter form would refuse a channel the API accepts.
          maxLength: maxLength(CHANNEL_MAX_LENGTH),
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
