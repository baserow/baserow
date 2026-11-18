<template>
  <div
    v-if="notification.sender?.user_type === 'identity'"
    role="img"
    :aria-label="$t('subjectType.identity')"
    :title="$t('subjectType.identity')"
  >
    <component
      :is="$registry.get('subject', 'auth.User').avatarComponent"
      :subject="notification.sender"
      size="medium"
    />
  </div>
  <div v-else class="notification-panel__notification-user-initials">
    {{ $filters.nameAbbreviation(notification.sender?.first_name) }}
  </div>
</template>

<script>
export default {
  name: 'NotificationSenderInitialsIcon',
  props: {
    notification: {
      type: Object,
      required: true,
    },
  },
}
</script>
