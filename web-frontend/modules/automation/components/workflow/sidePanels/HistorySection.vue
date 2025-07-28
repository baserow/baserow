<template>
  <Expandable toggle-on-click>
    <template #header="{ expanded }">
      <div class="history-section__header">
        <Icon
          v-if="props.item.status === 'success'"
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
import { useContext, computed } from '@nuxtjs/composition-api'
const { app } = useContext()

const props = defineProps({
  item: {
    type: Object,
    required: true,
  },
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

const humanCompletedDate = computed(() => {
  return moment.utc(props.item.completed_on).tz(getUserTimeZone()).fromNow()
})

const historyTitlePrefix = computed(() => {
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
      return app.i18n.t('historySidePanel.completedInLessThanSecond')
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
