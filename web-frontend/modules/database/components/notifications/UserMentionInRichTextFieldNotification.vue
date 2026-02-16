<template>
  <nuxt-link
    class="notification-panel__notification-link"
    :to="url"
    @click="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n-t keypath="userMentionInRichTextFieldNotification.title" tag="span">
        <template #sender>
          <strong v-if="sender">{{ sender }}</strong>
          <strong v-else
            ><s>{{
              $t('userMentionInRichTextFieldNotification.deletedUser')
            }}</s></strong
          >
        </template>
        <template #fieldName>
          <strong>{{ notification.data.field_name }}</strong>
        </template>
        <template #rowId>
          <strong>{{
            notification.data.row_name || notification.data.row_id
          }}</strong>
        </template>
        <template #tableName>
          <strong>{{ notification.data.table_name }}</strong>
        </template>
      </i18n-t>
    </div>
  </nuxt-link>
</template>

<script>
import notificationContent from '@baserow/modules/core/mixins/notificationContent'
import { tableRouteResetViewIfNeeded } from '@baserow/modules/database/utils/routing'

export default {
  name: 'UserMentionInRichTextFieldNotification',
  mixins: [notificationContent],
  props: {
    notification: {
      type: Object,
      required: true,
    },
  },
  emits: ['close-panel'],
  computed: {
    params() {
      return {
        databaseId: this.notification.data.database_id,
        tableId: this.notification.data.table_id,
        rowId: this.notification.data.row_id,
      }
    },
    url() {
      return tableRouteResetViewIfNeeded(this.params)
    },
  },
  methods: {
    handleClick() {
      this.$emit('close-panel')
    },
  },
}
</script>
