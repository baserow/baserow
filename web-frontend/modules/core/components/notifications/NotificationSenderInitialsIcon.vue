<template>
  <div class="notification-panel__notification-user-initials">
    {{ notification.sender?.first_name | nameAbbreviation }}
  </div>
</template>

<script>
export default {
  name: 'NotificationSenderInitialsIcon',
}
</script>
