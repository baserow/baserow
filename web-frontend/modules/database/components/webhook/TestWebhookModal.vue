<template>
  <Modal ref="modal" :tiny="true">
    <div class="webhook__test-title">{{ $t('testWebhookModal.title') }}</div>
    <Error :error="error" />
    <div v-if="isLoading" class="loading"></div>
    <div v-else-if="!error.visible">
      <div v-if="!!request" class="control">
        <div class="control__label">
          {{ $t('webhook.request') }}
        </div>
        <div class="control__elements">
          <div class="webhook__code-container">
            <pre
              class="webhook__code webhook__code--small"
            ><code>{{ request }}</code></pre>
          </div>
        </div>
      </div>
      <div v-if="!!response" class="control">
        <div class="control__label">
          {{ $t('webhook.response') }}
        </div>
        <div class="control__elements">
          <div class="webhook__code-container">
            <pre
              class="webhook__code webhook__code--small"
            ><code>{{ response }}</code></pre>
          </div>
        </div>
      </div>
      <div
        class="webhook__test-state"
        :class="{
          'webhook__test-state--ok': ok,
          'webhook__test-state--error': !ok,
        }"
      >
        {{ statusDescription }}
      </div>
    </div>
    <div v-if="!isLoading" class="actions margin-bottom-0">
      <a @click="hide()">{{ $t('action.cancel') }}</a>
      <div class="align-right">
        <Button
          type="secondary"
          @click="makeCall(lastTableId, lastEventType, lastWebhookValues)"
        >
          {{ $t('action.retry') }}
        </Button>
      </div>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import WebhookService from '@baserow/modules/database/services/webhook'

export default {
  name: 'TestWebhookModal',
  mixins: [modal, error],
  data() {
    return {
      lastTableId: null,
      lastEventType: null,
      lastWebhookValues: null,

      request: null,
      response: null,
      statusCode: null,
      isLoading: false,
    }
  },
  computed: {
    ok() {
      const status = this.statusCode
      return status !== null && status >= 200 && status <= 299
    },
    statusDescription() {
      if (this.statusCode === null) {
        return this.$t('testWebhookModal.unreachable')
      } else if (this.ok) {
        return `${this.statusCode} ${this.$t('webhook.status.statusOK')}`
      } else {
        return `${this.statusCode} ${this.$t('webhook.status.statusNotOK')}`
      }
    },
  },
  methods: {
    show(tableId, eventType, webhookValues, ...args) {
      this.getRootModal().show(...args)
      this.makeCall(tableId, eventType, webhookValues)
    },
    async makeCall(tableId, eventType, webhookValues) {
      this.lastTableId = tableId
      this.lastEventType = eventType
      this.lastWebhookValues = webhookValues
      this.isLoading = true
      this.hideError()

      webhookValues.event_type = eventType

      try {
        const { data } = await WebhookService(this.$client).testCall(
          tableId,
          webhookValues
        )

        this.request = data.request
        this.response = data.response
        this.statusCode = data.status_code
      } catch (e) {
        this.handleError(e, 'webhook', null, {
          url: {
            invalid_url: new ResponseErrorMessage(
              this.$t('webhook.form.invalidURLTitle'),
              this.$t('webhook.form.invalidURLDescription')
            ),
          },
        })
      }

      this.isLoading = false
    },
  },
}
</script>
