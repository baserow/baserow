<template>
  <!--
    Not an anchor like other notifications, because it contains the reported page
    link below, and anchors can't be nested.
  -->
  <div
    class="notification-panel__notification-link"
    @click="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n-t keypath="abuseReportCreatedNotification.title" tag="span">
        <template #resourceName>
          <strong>{{ notification.data.resource_name }}</strong>
        </template>
        <template #reporterEmail>
          <strong>{{ notification.data.reporter_email }}</strong>
        </template>
      </i18n-t>
    </div>
    <div class="notification-panel__notification-content-desc">
      <!--
        The link is rendered explicitly instead of making the whole notification
        navigate, so that an admin never opens a potentially malicious page
        without realizing it. It's rendered before the description so that it's
        always visible.
      -->
      <a
        :href="notification.data.public_url"
        target="_blank"
        rel="noopener noreferrer"
        @click.stop
      >
        {{ $t('abuseReportCreatedNotification.openResource') }}
      </a>
      <div class="abuse-report-notification__description">
        {{ truncatedDescription }}
      </div>
      <a
        v-if="descriptionIsTruncated"
        href="#"
        @click.prevent.stop="$refs.detailsModal.show()"
      >
        {{ $t('abuseReportCreatedNotification.showMore') }}
      </a>
      <Modal ref="detailsModal" small>
        <h2 class="box__title">
          {{ $t('abuseReportCreatedNotification.detailsTitle') }}
        </h2>
        <p>
          {{
            $t('abuseReportCreatedNotification.reportedBy', {
              reporterName: notification.data.reporter_name,
              reporterEmail: notification.data.reporter_email,
            })
          }}
        </p>
        <p class="abuse-report-notification__full-description">
          {{ notification.data.description }}
        </p>
        <a
          :href="notification.data.public_url"
          target="_blank"
          rel="noopener noreferrer"
        >
          {{ $t('abuseReportCreatedNotification.openResource') }}
        </a>
      </Modal>
    </div>
  </div>
</template>

<script>
import notificationContent from '@baserow/modules/core/mixins/notificationContent'

// Roughly two lines of text in the notification panel.
const DESCRIPTION_PREVIEW_LENGTH = 120

export default {
  name: 'AbuseReportCreatedNotification',
  mixins: [notificationContent],
  computed: {
    descriptionIsTruncated() {
      return (
        this.notification.data.description.length > DESCRIPTION_PREVIEW_LENGTH
      )
    },
    truncatedDescription() {
      const description = this.notification.data.description
      if (!this.descriptionIsTruncated) {
        return description
      }
      return `${description.slice(0, DESCRIPTION_PREVIEW_LENGTH)}…`
    },
  },
}
</script>
