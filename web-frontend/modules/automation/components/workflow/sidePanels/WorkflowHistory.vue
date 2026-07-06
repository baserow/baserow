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
          v-if="nodeHistoriesEntry === null"
          class="workflow-history__message"
        >
          <div class="loading"></div>
        </div>
        <template v-else>
          <NodeHistory
            v-for="nh in rootNodeHistories"
            :key="nh.id"
            :workflow-history-id="item.id"
            :node-history="nh"
            :child-node-histories-by-parent="childNodeHistoriesByParent"
            :error-descendant-node-ids="errorDescendantNodeIds"
            :pass-info-by-history-id="passInfoByHistoryId"
            :depth="0"
          />
          <div v-if="workflowLevelMessage" class="workflow-history__message">
            {{ workflowLevelMessage }}
          </div>
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
      <div
        v-if="workflowHistoryComponents.length"
        class="workflow-history__components"
      >
        <component
          :is="component"
          v-for="(component, index) in workflowHistoryComponents"
          :key="index"
          :workflow-history="item"
        />
      </div>
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
      // When the workflow run completes, if the WorkflowHistory is already
      // expanded, we should fetch the node histories.
      store.dispatch('automationHistory/fetchNodeHistories', {
        workflowHistoryId: props.item.id,
      })
    }
  },
  { immediate: true }
)

const onToggle = () => {
  if (props.item.status === 'started') return
  store.dispatch('automationHistory/fetchNodeHistories', {
    workflowHistoryId: props.item.id,
  })
}

const nodeHistoriesEntry = computed(() =>
  store.getters['automationHistory/getNodeHistories'](props.item.id)
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

const workflowHistoryComponents = computed(() => {
  return Object.values(app.$registry.getAll('plugin')).reduce(
    (components, plugin) =>
      components.concat(plugin.getWorkflowHistoryComponents(props.item)),
    []
  )
})

const historyTitlePrefix = computed(() => {
  return props.item.is_test_run === true
    ? `[${app.$i18n.t('historySidePanel.testRun')}] `
    : ''
})

/**
 * Return an array of root nodes, e.g. nodes that do not have a parent node.
 * They are rendered directly by WorkflowHistory. All other nodes are rendered
 * recursively by NodeHistory.
 */
const rootNodeHistories = computed(() => {
  const roots = []
  for (const nh of nodeHistoriesEntry.value ?? []) {
    if (nh.parent_node_id == null) {
      roots.push(nh)
    }
  }
  return roots
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
  for (const nodeHistory of nodeHistoriesEntry.value ?? []) {
    if (nodeHistory.parent_node_id != null) {
      const parent = nodeHistory.parent_node_id
      if (!_childNodeHistoriesByParent[parent])
        _childNodeHistoriesByParent[parent] = []
      _childNodeHistoriesByParent[parent].push(nodeHistory)
    }
  }
  return _childNodeHistoriesByParent
})

/**
 * Maps each node history id to its pass number and the total number of passes
 * for that node within this run. A node runs more than once when a "Go to node"
 * jump loops execution back to it. Passes are scoped by (node, iteration_path)
 * so iterator iterations aren't conflated with goto loop passes, and counted in
 * chronological order (the histories are returned ordered by started_on, id).
 */
const passInfoByHistoryId = computed(() => {
  const items = nodeHistoriesEntry.value ?? []

  const totals = {}
  for (const nh of items) {
    const key = `${nh.node}|${nh.iteration_path}`
    totals[key] = (totals[key] || 0) + 1
  }

  const counters = {}
  const result = {}
  for (const nh of items) {
    const key = `${nh.node}|${nh.iteration_path}`
    counters[key] = (counters[key] || 0) + 1
    result[nh.id] = { pass: counters[key], total: totals[key] }
  }
  return result
})

/**
 * Precomputed set of parent node IDs that have at least one errored
 * node history in their descendant subtree.
 */
const errorDescendantNodeIds = computed(() => {
  const items = nodeHistoriesEntry.value ?? []
  const nodesParents = new Map()
  for (const nh of items) {
    if (!nodesParents.has(nh.node)) {
      nodesParents.set(nh.node, nh.parent_node_id)
    }
  }

  const parentsWithErroredChild = new Set()
  for (const nh of items) {
    if (nh.status !== 'error') continue

    // We exclude the node itself so that different iterations of the same
    // node aren't tied to each other's own error status.
    let current = nodesParents.get(nh.node)

    // If a parent has already been marked as having an errored child, we
    // stop early to avoid unnecessary walks - since all of its ancestors
    // have already been marked.
    while (current != null && !parentsWithErroredChild.has(current)) {
      parentsWithErroredChild.add(current)
      current = nodesParents.get(current)
    }
  }
  return parentsWithErroredChild
})

/**
 * Surfaces a workflow-history message that isn't reflected on any node history.
 *
 * Today every workflow-level error raised after dispatch begins is also written
 * to the corresponding node history (so NodeHistory renders it and this returns
 * null to avoid duplication). The remaining messages are pre-dispatch failures
 * (e.g. rate limited, disabled after too many errors, before-run errors) which
 * have no node histories at all. This computed is therefore also a forward-safe
 * guard: should we ever log a workflow-level error after dispatch that no node
 * carries, its message still gets surfaced here instead of being swallowed.
 */
const workflowLevelMessage = computed(() => {
  if (!props.item.message) return null
  const hasErroredNode = (nodeHistoriesEntry.value ?? []).some(
    (nh) => nh.status === 'error'
  )
  return hasErroredNode ? null : props.item.message
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
