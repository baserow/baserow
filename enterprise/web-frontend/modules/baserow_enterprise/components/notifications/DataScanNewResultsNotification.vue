<template>
  <nuxt-link
    class="notification-panel__notification-link"
    :to="route"
    @click="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n-t :keypath="titleKey" tag="span">
        <template #count>
          <strong>{{ notification.data.new_results_count }}</strong>
        </template>
        <template #scanName>
          <strong>{{ notification.data.scan_name }}</strong>
        </template>
      </i18n-t>
    </div>
    <div class="notification-panel__notification-content-description">
      {{ $t('dataScanNewResultsNotification.description') }}
    </div>
  </nuxt-link>
</template>

<script>
import notificationContent from '@baserow/modules/core/mixins/notificationContent'

export default {
  name: 'DataScanNewResultsNotification',
  emits: ['close-panel'],
  mixins: [notificationContent],
  computed: {
    titleKey() {
      return this.notification.data.new_results_count === 1
        ? 'dataScanNewResultsNotification.titleSingular'
        : 'dataScanNewResultsNotification.titlePlural'
    },
  },
  methods: {
    handleClick() {
      this.$emit('close-panel')
    },
  },
}
</script>
