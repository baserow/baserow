<template>
  <div class="webhook__list">
    <p v-if="webhooks.length === 0" class="margin-top-2">
      {{ $t('webhookList.noWebhooksMessage') }}
    </p>
    <Webhook
      v-for="webhook in webhooks"
      :key="webhook.id"
      :webhook="webhook"
      :database="database"
      :table="table"
      :fields="fields"
      :views="views"
      @updated="$emit('updated', $event)"
      @deleted="$emit('deleted', $event)"
    />
  </div>
</template>

<script>
import Webhook from './Webhook.vue'

export default {
  name: 'WebhookList',
  components: {
    Webhook,
  },
  props: {
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
    webhooks: {
      type: Array,
      required: true,
    },
  },
}
</script>
