<template>
  <nuxt-link
    class="notification-panel__notification-link"
    :to="route"
    @click="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n-t keypath="rowCommentNotification.title" tag="span">
        <template #sender>
          <strong v-if="sender">{{ sender }}</strong>
          <strong v-else
            ><s>{{ $t('rowCommentNotification.deletedUser') }}</s></strong
          >
        </template>
        <template #row>
          <strong>{{
            notification.data.row_name || notification.data.row_id
          }}</strong>
        </template>
        <template #table>
          <strong>{{ notification.data.table_name }}</strong>
        </template>
      </i18n-t>
    </div>
    <RichTextEditor
      :editable="false"
      :mentionable-users="workspace.users"
      :value="notification.data.message"
    />
  </nuxt-link>
</template>

<script>
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor.vue'
import notificationContent from '@baserow/modules/core/mixins/notificationContent'

export default {
  name: 'RowCommentNotification',
  components: {
    RichTextEditor,
  },
  mixins: [notificationContent],
  emits: ['close-panel'],
  methods: {
    handleClick(evt) {
      this.$emit('close-panel')
    },
  },
}
</script>
