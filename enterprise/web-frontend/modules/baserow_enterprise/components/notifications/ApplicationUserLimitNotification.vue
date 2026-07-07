<template>
  <a
    href="#"
    class="notification-panel__notification-link"
    @click="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n-t v-if="limitReached" :keypath="reachedKeypath" tag="span">
        <template #workspaceName>
          <strong>{{ notification.data.workspace_name }}</strong>
        </template>
      </i18n-t>
      <i18n-t
        v-else
        keypath="applicationUserLimitNotification.titleWarning"
        tag="span"
      >
        <template #threshold>
          <strong>{{ notification.data.threshold }}%</strong>
        </template>
        <template #workspaceName>
          <strong>{{ notification.data.workspace_name }}</strong>
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
    reachedKeypath() {
      // When the limit is enforced (hard limit) new users can't sign in, otherwise
      // the limit is soft and we only prompt to upgrade.
      return this.notification.data.enforced
        ? 'applicationUserLimitNotification.titleReachedEnforced'
        : 'applicationUserLimitNotification.titleReached'
    },
  },
}
</script>
