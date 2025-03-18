<template>
  <div class="webhook" :class="{ 'webhook--open': isExpanded }">
    <div class="webhook__head">
      <div class="webhook__head-left">
        <div class="webhook__head-name">
          {{ webhook.name }}
        </div>
        <div class="webhook__head-details">
          <div class="webhook__head-details-target">
            {{ webhook.url }}
          </div>
          <a href="#" class="webhook__head-toggle" @click="toggleExpand()">
            {{ $t('webhook.details') }}
            <i
              class="webhook__head-toggle-icon"
              :class="{
                'iconoir-nav-arrow-down': !isExpanded,
                'iconoir-nav-arrow-up': isExpanded,
              }"
            ></i>
          </a>
        </div>
      </div>
      <div class="webhook__head-right">
        <div class="webhook__head-trigger">
          {{
            $tc('webhook.triggerDescription', calculateNumberOfEvents, {
              count: calculateNumberOfEvents,
            })
          }}
        </div>
        <div class="webhook__head-call">
          <div class="webhook__head-date">
            {{ $t('webhook.lastCall', { lastCallTime }) }}
          </div>
          <span
            class="webhook__head-call-state"
            :class="{
              'webhook__head-call-state--ok': lastCallOk,
              'webhook__head-call-state--error': !lastCallOk,
            }"
            >{{ lastCallStatusDescription }}</span
          >
        </div>
      </div>
    </div>
    <div class="webhook__body">
      <Tabs>
        <Tab :title="$t('action.edit')">
          <UpdateWebhook
            :webhook="webhook"
            :database="database"
            :table="table"
            :fields="fields"
            :views="views"
            @updated="$emit('updated', $event)"
            @deleted="$emit('deleted', $event)"
          />
        </Tab>
        <Tab :title="$t('webhook.callLog')">
          <p v-if="webhook.calls.length <= 0">{{ $t('webhook.noCalls') }}</p>
          <WebhookCall
            v-for="call in webhook.calls"
            :key="call.id"
            :call="call"
          />
        </Tab>
      </Tabs>
    </div>
  </div>
</template>

<script>
import moment from '@baserow/modules/core/moment'
import UpdateWebhook from '@baserow/modules/database/components/webhook/UpdateWebhook'
import WebhookCall from '@baserow/modules/database/components/webhook/WebhookCall'

export default {
  name: 'Webhook',
  components: { UpdateWebhook, WebhookCall },
  props: {
    webhook: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    views: {
      type: Array,
      required: true,
    },
  },
  data() {
    return {
      isExpanded: false,
    }
  },
  computed: {
    lastCallEvent() {
      const calls = this.webhook.calls
      return calls.length > 0 ? calls[0] : null
    },
    lastCallTime() {
      if (this.lastCallEvent) {
        return moment(this.lastCallEvent.called_time).format(
          'YYYY-MM-DD HH:mm:ss'
        )
      } else {
        return this.$t('webhook.noCalls')
      }
    },
    lastCallOk() {
      return (
        this.lastCallEvent !== null &&
        this.lastCallEvent.response_status >= 200 &&
        this.lastCallEvent.response_status <= 299
      )
    },
    lastCallStatusDescription() {
      const call = this.lastCallEvent

      if (call === null) {
        return ''
      }

      let description = ''
      if (call.response_status !== null) {
        description += call.response_status + ' '
      }

      description += this.lastCallOk
        ? this.$t('webhook.status.statusOK')
        : this.$t('webhook.status.statusNotOK')

      return description
    },
    calculateNumberOfEvents() {
      if (this.webhook.include_all_events) {
        return 0
      } else {
        return this.webhook.events.length
      }
    },
  },
  methods: {
    toggleExpand() {
      this.isExpanded = !this.isExpanded
    },
  },
}
</script>
