<template>
  <a
    href="#"
    class="notification-panel__notification-link"
    @click="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n-t :keypath="titleKeypath" tag="span">
        <template #workspaceName>
          <strong>{{ notification.data.workspace_name }}</strong>
        </template>
        <template #usage>
          <strong>{{ notification.data.usage }}</strong>
        </template>
        <template #limit>
          <strong>{{ notification.data.limit }}</strong>
        </template>
      </i18n-t>
    </div>
  </a>
</template>

<script>
import notificationContent from '@baserow/modules/core/mixins/notificationContent'

export default {
  name: 'ApplicationUserLimitNotification',
  mixins: [notificationContent],
  computed: {
    limitReached() {
      return this.notification.data.threshold >= 100
    },
    /**
     * An instance wide limit (from a license) is reached by the instance as a
     * whole, possibly because of another workspace, so the wording says so instead
     * of blaming the notified workspace. A per workspace limit (a subscription
     * quota) is the workspace's own.
     */
    instanceWide() {
      return Boolean(this.notification.data.instance_wide)
    },
    titleKeypath() {
      const scope = this.instanceWide ? 'Instance' : ''
      const level = this.limitReached ? 'titleReached' : 'titleWarning'
      return `applicationUserLimitNotification.${level}${scope}`
    },
  },
}
</script>
