<template>
  <nuxt-link
    class="notification-panel__notification-link"
    :to="route"
    @click.native="markAsReadAndHandleClick"
  >
    <div class="notification-panel__notification-content-title">
      <i18n path="formSubmittedNotification.title" tag="span">
        <template #formName>
          <strong>{{ notification.data.form_name }}</strong>
        </template>
        <template #tableName>
          <strong>{{ notification.data.table_name }}</strong>
        </template>
      </i18n>
    </div>
    <div class="notification-panel__notification-content-desc">
      <ul class="notification-panel__notification-content-summary">
        <li v-for="(elem, index) in submittedValuesSummary" :key="index">
          <span class="notification-panel__notification-content-summary-item"
            >{{ elem.field }}: {{ elem.value }}</span
          >
        </li>
      </ul>
      <div v-if="hiddenFieldsCount > 0">
        {{
          $tc('formSubmittedNotification.moreValues', hiddenFieldsCount, {
            count: hiddenFieldsCount,
          })
        }}
      </div>
    </div>
  </nuxt-link>
</template>

<script>
import notificationContent from '@baserow/modules/core/mixins/notificationContent'

export default {
  name: 'FormSubmittedNotification',
  mixins: [notificationContent],
  data() {
    return {
      limitValues: 3, // only the first 3 elements to keep it short
    }
  },
  computed: {
    submittedValuesSummary() {
      return this.notification.data.values
        .slice(0, this.limitValues)
        .map((elem) => {
          return { field: elem[0], value: elem[1] }
        })
    },
    hiddenFieldsCount() {
      return Math.max(
        0,
        this.notification.data.values.length - this.limitValues
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
