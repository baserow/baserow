<template>
  <a
    href="#"
    class="notification-panel__notification-link"
    @click="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n-t
        keypath="workspaceInvitationRejectedNotification.title"
        tag="span"
      >
        <template #sender>
          <strong v-if="sender">{{ sender }}</strong>
          <strong v-else
            ><s>{{
              $t('workspaceInvitationRejectedNotification.deletedUser')
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
  name: 'WorkspaceInvitationRejectedNotification',
  mixins: [notificationContent],
}
</script>
