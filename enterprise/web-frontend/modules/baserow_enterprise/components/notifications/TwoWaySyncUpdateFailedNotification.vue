<template>
  <nuxt-link
    class="notification-panel__notification-link"
    :to="route"
    @click.native="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n path="twoWaySyncUpdateFailed.title" tag="span">
        <template #name>
          <strong>{{ notification.data.table_name }}</strong>
        </template>
        <template #error>
          {{ notification.data.error }}
        </template>
      </i18n>
    </div>
  </nuxt-link>
</template>

<script>
import notificationContent from '@baserow/modules/core/mixins/notificationContent'

export default {
  name: 'TwoWaySyncUpdateFailed',
  mixins: [notificationContent],
  methods: {
    handleClick() {
      this.$emit('close-panel')
    },
  },
}
</script>
