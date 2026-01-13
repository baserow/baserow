<template>
  <nuxt-link
    class="notification-panel__notification-link"
    :to="route"
    @click="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n-t keypath="twoWaySyncUpdateFailed.title" tag="span">
        <template #name>
          <strong>{{ notification.data.table_name }}</strong>
        </template>
        <template #error>
          {{ notification.data.error }}
        </template>
      </i18n-t>
    </div>
  </nuxt-link>
</template>

<script>
import notificationContent from '@baserow/modules/core/mixins/notificationContent'

export default {
  name: 'TwoWaySyncUpdateFailed',
  emits: ['close-panel'],
  mixins: [notificationContent],
  methods: {
    handleClick() {
      this.$emit('close-panel')
    },
  },
}
</script>
