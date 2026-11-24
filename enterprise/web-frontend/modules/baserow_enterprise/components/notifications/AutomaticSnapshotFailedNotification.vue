<template>
  <nuxt-link
    class="notification-panel__notification-link"
    :to="route"
    @click="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n-t
        scope="global"
        keypath="automaticSnapshotFailedNotification.title"
        tag="span"
      >
        <template #name>
          <strong>{{ notification.data.application_name }}</strong>
        </template>
      </i18n-t>
    </div>
    <div class="notification-panel__notification-content-desc">
      {{
        $t('automaticSnapshotFailedNotification.description', {
          error: notification.data.error,
        })
      }}
    </div>
  </nuxt-link>
</template>

<script>
import notificationContent from '@baserow/modules/core/mixins/notificationContent'

export default {
  name: 'AutomaticSnapshotFailedNotification',
  mixins: [notificationContent],
  emits: ['close-panel'],
  methods: {
    handleClick() {
      this.$emit('close-panel')
    },
  },
}
</script>
