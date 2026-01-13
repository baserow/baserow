<template>
  <nuxt-link
    class="notification-panel__notification-link"
    :to="isLicenseUnavailable ? '' : route"
    @click="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n-t
        :path="
          isLicenseUnavailable
            ? 'periodicDataSyncDeactivatedNotification.licenseUnavailable'
            : 'periodicDataSyncDeactivatedNotification.failure'
        "
        tag="span"
      >
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
  name: 'PeriodicDataSyncDeactivatedNotification',
  emits: ['close-panel'],
  mixins: [notificationContent],
  computed: {
    isLicenseUnavailable() {
      return (
        this.notification.data.deactivation_reason === 'LICENSE_UNAVAILABLE'
      )
    },
  },
  methods: {
    handleClick() {
      this.$emit('close-panel')
    },
  },
}
</script>
