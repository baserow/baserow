<template>
  <Expandable>
    <template #header="{ toggle, expanded }">
      <div class="history__section">
        <a class="history__status" @click="toggle">
          <div class="history__status-heading">
            <i :class="statusIconClass" />
            <span class="history__status-heading-title">
              {{ statusTitle }}
            </span>
          </div>

          <span class="history__date">{{ completedDate }}</span>

          <i
            class="history__collapse"
            :class="{
              'iconoir-nav-arrow-down': expanded,
              'iconoir-nav-arrow-right': !expanded,
            }"
          />
        </a>
      </div>
    </template>

    <template #default>
      <div v-if="item.message" class="history__message">
        {{ item.message }}
      </div>
    </template>
  </Expandable>
</template>

<script setup>
import moment from '@baserow/modules/core/moment'
import { getUserTimeZone } from '@baserow/modules/core/utils/date'
import { useContext, computed } from '@nuxtjs/composition-api'
const { app } = useContext()

const props = defineProps({
  item: {
    type: Object,
    required: true,
  },
})

const statusIconClass = computed(() => {
  switch (props.item.status) {
    case 'success':
      return 'history__icon--success iconoir-check-circle'
    case 'error':
      return 'history__icon--error iconoir-warning-circle'
    default:
      return 'history__icon--disabled iconoir-warning-circle'
  }
})

const statusTitle = computed(() => {
  switch (props.item.status) {
    case 'success':
      return app.i18n.t('historySidePanel.statusSuccess')
    case 'error':
      return app.i18n.t('historySidePanel.statusError')
    default:
      return app.i18n.t('historySidePanel.statusDisabled')
  }
})

const completedDate = computed(() => {
  return moment
    .utc(props.item.completed_on)
    .tz(getUserTimeZone())
    .format('YYYY-MM-DD HH:mm:ss')
})
</script>
