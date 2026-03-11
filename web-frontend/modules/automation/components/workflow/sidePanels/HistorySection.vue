<template>
  <Expandable toggle-on-click>
    <template #header="{ expanded }">
      <div class="history-section__header">
        <Icon
          v-if="props.item.status === 'started'"
          icon="iconoir-refresh-double"
          type="secondary"
        />
        <Icon
          v-else-if="props.item.status === 'success'"
          icon="iconoir-check-circle"
          type="success"
        />
        <Icon v-else icon="iconoir-warning-circle" type="error" />
        <span class="history-section__header-title">
          {{ historyTitlePrefix }}{{ statusTitle }}
        </span>
        <span :title="completedDate" class="history-section__header-date">
          {{ humanCompletedDate }}
        </span>
        <Icon
          :icon="
            expanded ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right'
          "
          type="secondary"
        />
      </div>
    </template>

    <template #default>
      <div class="history-section__message">
        {{ historyMessage }}
      </div>
    </template>
  </Expandable>
</template>

<script setup>
import moment from '@baserow/modules/core/moment'
import { getUserTimeZone } from '@baserow/modules/core/utils/date'

const app = useNuxtApp()

const props = defineProps({
  item: {
    type: Object,
    required: true,
  },
})

const statusTitle = computed(() => {
  switch (props.item.status) {
    case 'started':
      return app.$i18n.t('historySidePanel.statusStarted')
    case 'success':
      return app.$i18n.t('historySidePanel.statusSuccess')
    case 'disabled':
      return app.$i18n.t('historySidePanel.statusDisabled')
    default:
      return app.$i18n.t('historySidePanel.statusError')
  }
})

const completedDate = computed(() => {
  const date =
    props.item.status === 'started'
      ? props.item.started_on
      : props.item.completed_on
  return moment.utc(date).tz(getUserTimeZone()).format('YYYY-MM-DD HH:mm:ss')
})

const humanCompletedDate = computed(() => {
  const date =
    props.item.status === 'started'
      ? props.item.started_on
      : props.item.completed_on
  if (props.item.status === 'started') {
    return moment.utc(date).tz(getUserTimeZone()).fromNow()
  }
  return moment.utc(date).tz(getUserTimeZone()).fromNow()
})

const historyTitlePrefix = computed(() => {
  return props.item.is_test_run === true
    ? `[${app.$i18n.t('historySidePanel.testRun')}] `
    : ''
})

const historyMessage = computed(() => {
  if (props.item.status === 'success') {
    const start = new Date(props.item.started_on)
    const end = new Date(props.item.completed_on)

    const deltaMs = end - start
    if (deltaMs < 1000) {
      return app.$i18n.t('historySidePanel.completedInLessThanSecond')
    } else {
      const deltaSeconds = deltaMs / 1000
      return app.$i18n.t('historySidePanel.completedInSeconds', {
        s: deltaSeconds.toFixed(2),
      })
    }
  } else if (props.item.status === 'started') {
    const start = new Date(props.item.started_on)
    const end = new Date()

    const deltaMs = end - start
    const deltaSeconds = deltaMs / 1000
    return app.$i18n.t('historySidePanel.running', {
      at: deltaSeconds.toFixed(2),
    })
  } else {
    return props.item.message
  }
})
</script>
