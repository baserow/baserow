<template>
  <div class="notification-panel__notification-user-initials">
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
