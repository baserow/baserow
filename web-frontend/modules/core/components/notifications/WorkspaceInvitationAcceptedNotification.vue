<template>
  <a
    href="#"
    class="notification-panel__notification-link"
    @click="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n-t
        keypath="workspaceInvitationAcceptedNotification.title"
        tag="span"
      >
        <template #sender>
          <strong v-if="sender">{{ sender }}</strong>
          <strong v-else
            ><s>{{
              $t('workspaceInvitationAcceptedNotification.deletedUser')
            }}</s></strong
          >
        </template>
        <template #workspaceName>
          <strong>{{ notification.data.invited_to_workspace_name }}</strong>
        </template>
      </i18n-t>
    </div>
  </a>
</template>

<script>
import notificationContent from '@baserow/modules/core/mixins/notificationContent'

export default {
  name: 'WorkspaceInvitationAcceptedNotification',
  mixins: [notificationContent],
}
</script>
