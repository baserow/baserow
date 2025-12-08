<template>
  <a
    class="notification-panel__notification-link"
    :href="notification.data.release_notes_url"
    target="_blank"
    rel="noopener noreferrer"
    @click="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n-t keypath="versionUpgradeNotification.title" tag="span">
        <template #version>
          <strong>{{ `Baserow ${notification.data.version}` }}</strong>
        </template>
      </i18n-t>
    </div>
  </a>
</template>

<script>
import notificationContent from '@baserow/modules/core/mixins/notificationContent'

export default {
  name: 'BaserowVersionUpgradeNotification',
  mixins: [notificationContent],
}
</script>
