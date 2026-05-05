<template>
  <Expandable toggle-on-click>
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
          v-if="!item.node_histories.length && item.message"
          class="workflow-history__message"
        >
          {{ item.message }}
        </div>
        <NodeHistory
          v-for="nodeId in rootNodeIds"
          v-else
          :key="nodeId"
          :node-id="nodeId"
          :node-histories="nodeHistoriesByNode[nodeId] || []"
          :child-node-histories-by-parent="childNodeHistoriesByParent"
          :depth="0"
        />
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
import moment from '@baserow/modules/core/moment'
import { getUserTimeZone } from '@baserow/modules/core/utils/date'

import historySuccessIcon from '@baserow/modules/core/assets/images/history-success.svg?url'
import historyFailedIcon from '@baserow/modules/core/assets/images/history-failed.svg?url'
import historyDisabledIcon from '@baserow/modules/core/assets/images/history-disabled.svg?url'
import NodeHistory from '@baserow/modules/automation/components/workflow/sidePanels/NodeHistory.vue'

const app = useNuxtApp()

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

/**
 * Return an array of root node IDs, e.g. nodes that do not have a parent node.
 *
 * WorkflowHistory only renders the root nodes directly via NodeHistory.
 * NodeHistory then renders any child nodes recursively. This makes it easy
 * to correctly nest child nodes as well as their expandable content.
 */
const rootNodeIds = computed(() => {
  const _rootNodeIds = []
  for (const nodeHistory of props.item.node_histories) {
    if (
      nodeHistory.parent_node_id == null &&
      !_rootNodeIds.includes(nodeHistory.node)
    ) {
      _rootNodeIds.push(nodeHistory.node)
    }
  }
  return _rootNodeIds
})

/**
 * Return an object where keys are node IDs and values are an array of node
 * histories for that node.
 *
 * This is used to show the correct histories (node status, run number) are
 * shown in the NodeHistory.
 */
const nodeHistoriesByNode = computed(() => {
  const _nodeHistoriesByNode = {}
  for (const nodeHistory of props.item.node_histories) {
    if (!_nodeHistoriesByNode[nodeHistory.node]) {
      _nodeHistoriesByNode[nodeHistory.node] = []
    }
    _nodeHistoriesByNode[nodeHistory.node].push(nodeHistory)
  }
  return _nodeHistoriesByNode
})

/**
 * Return an object where keys are parent node IDs and values are an array
 * of child node histories for that node.
 *
 * This is used to determine if a node has children, as well as the number of
 * runs for a collection node.
 */
const childNodeHistoriesByParent = computed(() => {
  const _childNodeHistoriesByParent = {}
  for (const nodeHistory of props.item.node_histories) {
    if (nodeHistory.parent_node_id != null) {
      const parent = nodeHistory.parent_node_id
      if (!_childNodeHistoriesByParent[parent])
        _childNodeHistoriesByParent[parent] = []
      _childNodeHistoriesByParent[parent].push(nodeHistory)
    }
  }
  return _childNodeHistoriesByParent
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
