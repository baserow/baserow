<template>
  <nuxt-link
    class="notification-panel__notification-link"
    :to="route"
    @click="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n-t keypath="whiteboardCommentMentionNotification.title" tag="span">
        <template #sender>
          <strong v-if="sender">{{ sender }}</strong>
          <strong v-else>
            <s>{{ $t('whiteboardCommentMentionNotification.deletedUser') }}</s>
          </strong>
        </template>
        <template #whiteboard>
          <strong>{{ notification.data.whiteboard_name }}</strong>
        </template>
      </i18n-t>
    </div>
    <RichTextEditor
      :editable="false"
      :mentionable-users="workspace.users"
      :model-value="notification.data.message"
    />
  </nuxt-link>
</template>

<script>
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor.vue'
import notificationContent from '@baserow/modules/core/mixins/notificationContent'

export default {
  name: 'WhiteboardCommentMentionNotification',
  components: { RichTextEditor },
  mixins: [notificationContent],
  emits: ['close-panel'],
  methods: {
    handleClick() {
      this.$emit('close-panel')
    },
  },
}
</script>
