<template>
  <div>
    <nuxt-link
      class="notification-panel__notification-link"
      :to="route"
      @click="markAsReadAndHandleClick"
    >
      <div
        class="notification-panel__notification-content-title user-template-notification__title"
      >
        <i18n-t scope="global" :keypath="titleKey" tag="span">
          <template #author>
            <strong>{{ notification.data.author_name }}</strong>
          </template>
          <template #name>
            <strong>{{ notification.data.template_name }}</strong>
          </template>
        </i18n-t>
      </div>
      <div
        v-if="notification.data.reason"
        class="notification-panel__notification-content-desc user-template-notification__reason"
        :class="{ 'user-template-notification__reason--cut': reasonIsCut }"
      >
        {{ reasonPreview }}
      </div>
    </nuxt-link>
    <template v-if="reasonIsCut">
      <a
        href="#"
        class="user-template-notification__show-more"
        @click.prevent="$refs.reasonModal.show()"
      >
        {{ $t('userTemplateNotification.showMore') }}
      </a>
      <Modal ref="reasonModal" small>
        <h2 class="box__title">
          {{ $t('userTemplateNotification.reasonTitle') }}
        </h2>
        <p class="user-template-notification__full-reason">
          {{ notification.data.reason }}
        </p>
      </Modal>
    </template>
  </div>
</template>

<script>
import notificationContent from '@baserow/modules/core/mixins/notificationContent'

const REASON_PREVIEW_LENGTH = 120

export default {
  name: 'UserTemplateNotification',
  mixins: [notificationContent],
  emits: ['close-panel'],
  computed: {
    titleKey() {
      return this.$registry
        .get('notification', this.notification.type)
        .getTitleKey()
    },
    reasonIsCut() {
      return this.notification.data.reason?.length > REASON_PREVIEW_LENGTH
    },
    reasonPreview() {
      const reason = this.notification.data.reason
      return this.reasonIsCut
        ? `${reason.slice(0, REASON_PREVIEW_LENGTH)}…`
        : reason
    },
  },
  methods: {
    handleClick() {
      this.$emit('close-panel')
    },
  },
}
</script>
