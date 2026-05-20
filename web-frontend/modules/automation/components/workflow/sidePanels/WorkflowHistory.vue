<template>
  <Expandable toggle-on-click @toggle="onToggle">
    <template #header="{ expanded }">
      <div class="workflow-history__divider"></div>
      <div class="workflow-history__header">
        <img :src="historyIconPath" width="16" height="16" />
        <span class="workflow-history__header-title">
          {{ historyTitlePrefix }}{{ statusTitle }}
        </span>
        <span
          v-if="item.completed_on"
          :title="completedDate"
          class="workflow-history__header-date"
        >
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
      <template v-if="item.status !== 'started'">
        <div
          v-if="nodeHistoriesEntry.status === STATUS_LOADING"
          class="workflow-history__message"
        >
          <div class="loading"></div>
        </div>
        <div
          v-else-if="nodeHistoriesEntry.status === STATUS_ERROR"
          class="workflow-history__message"
        >
          {{ $t('historySidePanel.failedToLoad') }}
        </div>
        <template v-else>
          <div
            v-if="!nodeHistoriesEntry.items.length && item.message"
            class="workflow-history__message"
          >
            {{ item.message }}
          </div>
          <NodeHistory
            v-for="nodeHistory in nodeHistoriesEntry.items"
            v-else
            :key="nodeHistory.id"
            :workflow-history-id="item.id"
            :node-history="nodeHistory"
          />
        </template>
        <div class="workflow-history__run-time">
          {{ totalRunTimeMessage }}
        </div>
      </template>
      <template v-else>
        <div class="workflow-history__run-time">
          {{ totalRunTimeMessage }}
        </div>
      </template>
    </template>
  </Expandable>
</template>

<script setup>
import { useStore } from 'vuex'
import moment from '@baserow/modules/core/moment'
import { getUserTimeZone } from '@baserow/modules/core/utils/date'

import historySuccessIcon from '@baserow/modules/core/assets/images/history-success.svg?url'
import historyFailedIcon from '@baserow/modules/core/assets/images/history-failed.svg?url'
import historyDisabledIcon from '@baserow/modules/core/assets/images/history-disabled.svg?url'
import {
  STATUS_ERROR,
  STATUS_LOADING,
} from '@baserow/modules/automation/constants'
import NodeHistory from '@baserow/modules/automation/components/workflow/sidePanels/NodeHistory.vue'

const app = useNuxtApp()
const store = useStore()

const props = defineProps({
  item: {
    type: Object,
    required: true,
  },
})

const now = ref(new Date())
let timer = null

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

watch(
  () => props.item.status,
  (status) => {
    if (status === 'started') {
      timer = setInterval(() => {
        now.value = new Date()
      }, 1000)
    } else if (timer) {
      clearInterval(timer)
      timer = null
    }
  },
  { immediate: true }
)

const onToggle = () => {
  if (props.item.status === 'started') return
  store.dispatch('automationHistory/fetchNodeHistories', {
    workflowHistoryId: props.item.id,
    parentNodeId: null,
  })
}

const nodeHistoriesEntry = computed(() =>
  store.getters['automationHistory/getNodeHistoriesByParent'](props.item.id)
)

const statusTitle = computed(() => {
  switch (props.item.status) {
    case 'success':
      return app.$i18n.t('historySidePanel.statusSuccess')
    case 'error':
      return app.$i18n.t('historySidePanel.statusError')
    case 'started':
      return app.$i18n.t('historySidePanel.statusStarted')
    default:
      return app.$i18n.t('historySidePanel.statusDisabled')
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
    ? `[${app.$i18n.t('historySidePanel.testRun')}] `
    : ''
})

const historyIconPath = computed(() => {
  switch (props.item.status) {
    case 'success':
      return historySuccessIcon
    case 'error':
      return historyFailedIcon
    default:
      return historyDisabledIcon
  }
})

const totalRunTimeMessage = computed(() => {
  const start = new Date(props.item.started_on)

  if (props.item.status === 'started') {
    const deltaMs = now.value - start
    const deltaSeconds = deltaMs / 1000
    return app.$i18n.t('historySidePanel.running', {
      at: Math.floor(deltaSeconds),
    })
  } else {
    const end = new Date(props.item.completed_on)

    const deltaMs = end - start
    if (deltaMs < 1000) {
      return app.$i18n.t('historySidePanel.completedInLessThanSecond')
    } else {
      const deltaSeconds = deltaMs / 1000
      return app.$i18n.t('historySidePanel.completedInSeconds', {
        s: Math.floor(deltaSeconds),
      })
    }
  }
})
</script>
