<template>
  <nuxt-link
    class="notification-panel__notification-link"
    :to="route"
    @click="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n-t keypath="twoWaySyncDeactivated.title" tag="span">
        <template #name>
          <strong>{{ notification.data.table_name }}</strong>
        </template>
      </i18n-t>
    </div>
  </nuxt-link>
</template>

<script>
import notificationContent from '@baserow/modules/core/mixins/notificationContent'

export default {
  name: 'TwoWaySyncDeactivated',
  emits: ['close-panel'],
  mixins: [notificationContent],
  methods: {
    handleClick() {
      this.$emit('close-panel')
    },
  },
}
</script>
