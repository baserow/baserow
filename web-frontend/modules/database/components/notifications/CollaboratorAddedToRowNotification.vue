<template>
  <nuxt-link
    class="notification-panel__notification-link"
    :to="route"
    @click.native="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n path="collaboratorAddedToRowNotification.title" tag="span">
        <template #sender>
          <strong v-if="sender">{{ sender }}</strong>
          <strong v-else
            ><s>{{
              $t('collaboratorAddedToRowNotification.unknownUser')
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
      </i18n>
    </div>
  </nuxt-link>
</template>

<script>
import notificationContent from '@baserow/modules/core/mixins/notificationContent'

export default {
  name: 'CollaboratorAddedToRowNotification',
  mixins: [notificationContent],
  methods: {
    handleClick() {
      this.$emit('close-panel')
    },
  },
}
</script>
