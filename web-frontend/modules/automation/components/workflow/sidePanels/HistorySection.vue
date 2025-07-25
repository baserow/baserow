<template>
  <Expandable>
    <template #header="{ toggle, expanded }">
      <div class="history-section">
        <a class="history-section__status" @click="toggle">
          <div class="history-section__status-heading">
            <i :class="statusIconClass" />
            <span class="history-section__status-heading-title">
              {{ statusTitle }}
            </span>
          </div>

          <span class="history-section__date">{{ completedDate }}</span>

          <i
            class="history-section__collapse"
            :class="{
              'iconoir-nav-arrow-down': expanded,
              'iconoir-nav-arrow-right': !expanded,
            }"
          />
        </a>
      </div>
    </template>

    <template #default>
      <div class="history-section__message">
        {{ historyMessagePrefix }}{{ historyMessage }}
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
      return 'history-section__icon--success iconoir-check-circle'
    case 'error':
      return 'history-section__icon--error iconoir-warning-circle'
    default:
      return 'history-section__icon--disabled iconoir-warning-circle'
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

const historyMessagePrefix = computed(() => {
  return props.item.is_test_run === true
    ? `[${app.i18n.t('historySidePanel.testRun')}] `
    : ''
})

const historyMessage = computed(() => {
  if (props.item.status === 'success') {
    const start = new Date(props.item.started_on)
    const end = new Date(props.item.completed_on)

    const deltaMs = end - start
    if (deltaMs < 1000) {
      return app.i18n.t('historySidePanel.completedInMilliseconds', {
        ms: deltaMs.toFixed(2),
      })
    } else {
      const deltaSeconds = deltaMs / 1000
      return app.i18n.t('historySidePanel.completedInSeconds', {
        s: deltaSeconds.toFixed(2),
      })
    }
  } else {
    return props.item.message
  }
})
</script>
