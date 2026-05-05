<template>
  <nuxt-link
    class="notification-panel__notification-link"
    :to="route"
    @click="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n-t keypath="workflowDisabledNotification.body" tag="span">
        <template #name>
          <strong>{{ notification.data.workflow_name }}</strong>
        </template>
      </i18n-t>
    </div>
  </nuxt-link>
</template>

<script>
import notificationContent from '@baserow/modules/core/mixins/notificationContent'

export default {
  name: 'WorkflowDisabledNotification',
  mixins: [notificationContent],
  emits: ['close-panel'],
  methods: {
    handleClick() {
      this.$emit('close-panel')
    },
  },
}
</script>
