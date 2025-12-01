<template>
  <nuxt-link
    class="notification-panel__notification-link"
    :to="route"
    @click.native="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n path="twoWaySyncDeactivated.title" tag="span">
        <template #name>
          <strong>{{ notification.data.table_name }}</strong>
        </template>
      </i18n>
    </div>
  </nuxt-link>
</template>

<script>
import notificationContent from '@baserow/modules/core/mixins/notificationContent'

export default {
  name: 'TwoWaySyncDeactivated',
  mixins: [notificationContent],
  methods: {
    handleClick() {
      this.$emit('close-panel')
    },
  },
}
</script>
