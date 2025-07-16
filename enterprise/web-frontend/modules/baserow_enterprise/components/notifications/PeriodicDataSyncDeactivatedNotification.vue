<template>
  <nuxt-link
    class="notification-panel__notification-link"
    :to="route"
    @click.native="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n
        :path="
          isLicenseLoss
            ? 'periodicDataSyncDeactivatedNotification.licenseLoss'
            : 'periodicDataSyncDeactivatedNotification.failure'
        "
        tag="span"
      >
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
  name: 'PeriodicDataSyncDeactivatedNotification',
  mixins: [notificationContent],
  computed: {
    isLicenseLoss() {
      return this.notification.data.deactivation_reason === 'LICENSE_LOST'
    },
  },
  methods: {
    handleClick() {
      this.$emit('close-panel')
    },
  },
}
</script>
