<template>
  <nuxt-link
    class="notification-panel__notification-link"
    :to="route"
    @click.native="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n path="webhookPayloadTooLargeNotification.body" tag="span">
        <template #name>
          <strong>{{ notification.data.webhook_name }}</strong>
        </template>
        <template #event_id>
          <strong>{{ notification.data.event_id }}</strong>
        </template>
        <template #batch_limit>
          <strong>{{ notification.data.batch_limit }}</strong>
        </template>
      </i18n>
    </div>
  </nuxt-link>
</template>

<script>
import notificationContent from '@baserow/modules/core/mixins/notificationContent'

export default {
  name: 'WebhookPayloadTooLargeNotification',
  mixins: [notificationContent],
  methods: {
    handleClick() {
      this.$emit('close-panel')
    },
  },
}
</script>
