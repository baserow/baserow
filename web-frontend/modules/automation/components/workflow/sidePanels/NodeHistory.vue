<template>
  <div
    class="node-history__header"
    :style="depth > 0 ? { marginLeft: '24px' } : {}"
  >
    <Expandable v-if="hasChildren" toggle-on-click>
      <template #header="{ expanded }">
        <div class="node-history__header-row">
          <div class="node-history__header-icon">
            <i v-if="nodeIconClass" :class="nodeIconClass"></i>
            <img v-else :alt="nodeType.name" :src="nodeType.image" />
          </div>
          <div class="node-history__header-info">
            <div>
              <div
                class="node-history__header-info-type"
                :class="{
                  'node-history__header-info-type-error': status === 'error',
                }"
              >
                {{ nodeTypeLabel }}
              </div>
            </div>

            <span v-if="passLabel" class="node-history__header-info-pass">{{
              passLabel
            }}</span>

            <div>
              <Icon
                :icon="
                  expanded
                    ? 'iconoir-nav-arrow-down'
                    : 'iconoir-nav-arrow-right'
                "
                type="secondary"
              />
            </div>
          </div>

          <div class="node-history__spacer"></div>

          <Badge
            rounded
            :color="status === 'error' ? 'red' : 'green'"
            size="small"
          >
            {{ statusLabel }}
          </Badge>
        </div>
      </template>
      <template #default>
        <Expandable
          v-for="group in childNodeHistoriesByIteration"
          :key="group.iteration"
          toggle-on-click
        >
          <template #header="{ expanded }">
            <div
              class="node-history__header-row"
              :style="{ marginLeft: 48 + 'px' }"
            >
              <div class="node-history__header-info">
                <span
                  class="node-history__header-info-type"
                  :class="{
                    'node-history__header-info-type-error':
                      iterationHasError(group),
                  }"
                >
                  {{
                    $t('historySidePanel.runNumber', { n: group.iteration + 1 })
                  }}
                </span>
              </div>
              <div>
                <Icon
                  :icon="
                    expanded
                      ? 'iconoir-nav-arrow-down'
                      : 'iconoir-nav-arrow-right'
                  "
                  type="secondary"
                />
              </div>
            </div>
          </template>
          <template #default>
            <div class="node-history__nested-scroll">
              <div class="node-history__nested-scroll-inner">
                <NodeHistory
                  v-for="nh in group.histories"
                  :key="nh.id"
                  :workflow-history-id="workflowHistoryId"
                  :node-history="nh"
                  :child-node-histories-by-parent="childNodeHistoriesByParent"
                  :error-descendant-node-ids="errorDescendantNodeIds"
                  :pass-info-by-history-id="passInfoByHistoryId"
                  :depth="depth + 1"
                />
              </div>
            </div>
          </template>
        </Expandable>
      </template>
    </Expandable>

    <div v-else class="node-history__header-row">
      <div class="node-history__header-icon">
        <i v-if="nodeIconClass" :class="nodeIconClass"></i>
        <img v-else :alt="nodeType.name" :src="nodeType.image" />
      </div>
      <div class="node-history__header-info">
        <div
          class="node-history__header-info-type"
          :class="{
            'node-history__header-info-type-error': status === 'error',
          }"
        >
          {{ nodeTypeLabel }}
        </div>

        <span v-if="passLabel" class="node-history__header-info-pass">{{
          passLabel
        }}</span>

        <div class="node-history__header-show-result">
          <a
            ref="nodeResultButtonContextToggle"
            role="button"
            :title="$t('workflowNode.nodeOptions')"
            @click="openNodeResultButtonContext()"
          >
            <i class="baserow-icon-more-vertical"></i>
          </a>
        </div>
      </div>

      <div class="node-history__spacer"></div>

      <Badge rounded :color="status === 'error' ? 'red' : 'green'" size="small">
        {{ statusLabel }}
      </Badge>
    </div>

    <div v-if="hasOwnError" class="node-history__error">
      <div class="node-history__error-info">
        {{ errorMessage }}
      </div>

      <Expandable toggle-on-click>
        <template #header="{ expanded }">
          <div class="node-history__error-expand">
            <div class="node-history__error-expand-label">
              {{
                expanded
                  ? $t('historySidePanel.errorHideDetails')
                  : $t('historySidePanel.errorShowDetails')
              }}
            </div>

            <div>
              <Icon
                :icon="
                  expanded
                    ? 'iconoir-nav-arrow-down'
                    : 'iconoir-nav-arrow-right'
                "
                type="secondary"
              />
            </div>
          </div>
        </template>
        <template #default>
          <div class="node-history__error-expanded">
            {{ errorMessage }}
          </div>
        </template>
      </Expandable>
    </div>

    <Context v-if="!hasChildren" ref="nodeResultButtonContext">
      <Button
        ref="nodeResultContextToggle"
        type="secondary"
        full-width
        :loading="fetchingResult"
        icon="iconoir-code-brackets node-history__show-result-button-icon"
        @click="showNodeResultModal"
      >
        {{ $t('historySidePanel.showResult') }}
      </Button>
    </Context>

    <SampleDataModal
      v-if="!hasChildren"
      ref="nodeResultModal"
      :sample-data="resolvedSampleData"
      :title="nodeTypeLabel"
      :subtitle="$t('simulateDispatch.sampleDataModalSubTitle')"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useStore } from 'vuex'

import SampleDataModal from '@baserow/modules/core/components/SampleDataModal'
import { notifyIf } from '@baserow/modules/core/utils/error'

const app = useNuxtApp()
const store = useStore()

const props = defineProps({
  workflowHistoryId: {
    type: Number,
    required: true,
  },
  nodeHistory: {
    type: Object,
    required: true,
  },
  childNodeHistoriesByParent: {
    type: Object,
    default: () => ({}),
  },
  errorDescendantNodeIds: {
    type: Set,
    default: () => new Set(),
  },
  passInfoByHistoryId: {
    type: Object,
    default: () => ({}),
  },
  depth: {
    type: Number,
    default: 0,
  },
})

const nodeResultButtonContext = ref(null)
const nodeResultButtonContextToggle = ref(null)
const nodeResultModal = ref(null)
const fetchingResult = ref(false)
const resolvedSampleData = ref(null)

const nodeType = computed(() => {
  return app.$registry.get('node', props.nodeHistory.node_type)
})

const nodeIconClass = computed(() => {
  return nodeType.value.iconClass
})

/**
 * For a "Go to node" entry, resolve the label of the node it jumps to so the
 * history reads "Go to node → <destination>".
 *
 * We prefer the destination's stored label resolved by the backend (run-time
 * accurate). When the destination has no custom label, we fall back to the
 * generic name of its node type. We can't resolve the node from the editor
 * workflow by id, because the history references the published workflow copy
 * that ran, whose node ids differ from the editor's.
 */
const destinationLabel = computed(() => {
  if (props.nodeHistory.node_type !== 'goto') return null

  if (props.nodeHistory.destination_label) {
    return props.nodeHistory.destination_label
  }

  const destinationType = props.nodeHistory.destination_node_type
  if (!destinationType) return null

  if (!app.$registry.exists('node', destinationType)) return null
  return app.$registry.get('node', destinationType).name
})

const nodeTypeLabel = computed(() => {
  const baseLabel = props.nodeHistory.node_label || nodeType.value.name
  if (props.nodeHistory.node_type === 'router') {
    // Show which branch was taken.
    const edgeLabel =
      props.nodeHistory.edge_label ||
      app.$i18n.t('nodeType.defaultEdgeLabelFallback')
    return `${baseLabel} (${edgeLabel})`
  }
  if (props.nodeHistory.node_type === 'goto' && destinationLabel.value) {
    // Show which node the workflow jumps to.
    return `${baseLabel} → ${destinationLabel.value}`
  }
  return baseLabel
})

/**
 * When a node runs more than once within a single run (e.g. a "Go to node" jump
 * loops back to it), show which pass this entry corresponds to, e.g. "Run 2".
 */
const passLabel = computed(() => {
  const info = props.passInfoByHistoryId?.[props.nodeHistory.id]
  if (!info || info.total <= 1) return null
  return app.$i18n.t('historySidePanel.runNumber', { n: info.pass })
})

const iterationHasError = (group) => {
  return group.histories.some(
    (h) => h.status === 'error' || props.errorDescendantNodeIds.has(h.node)
  )
}

const hasOwnError = computed(() => props.nodeHistory.status === 'error')

const status = computed(() => {
  const childError = props.errorDescendantNodeIds.has(props.nodeHistory.node)
  return hasOwnError.value || childError ? 'error' : 'success'
})

const statusLabel = computed(() => {
  return status.value === 'success'
    ? app.$i18n.t('historySidePanel.statusSuccessBadge')
    : app.$i18n.t('historySidePanel.statusErrorBadge')
})

const errorMessage = computed(() => props.nodeHistory.message)

/**
 * Direct children of this node that belong to this node's iteration.
 */
const childNodeHistories = computed(() => {
  const allChildHistories =
    props.childNodeHistoriesByParent[props.nodeHistory.node]
  if (!allChildHistories) return []

  // This node's own iteration_path
  const ownPath = props.nodeHistory.iteration_path

  return allChildHistories.filter((child) => {
    const childPath = child.iteration_path

    const lastDotIndex = childPath.lastIndexOf('.')
    // Strip the child's last segment (its own iteration index) to get the
    // path of the iteration it belongs to. A child at depth 1 has no dot,
    // so its parent's path is "".
    const parentPath = lastDotIndex >= 0 ? childPath.slice(0, lastDotIndex) : ''
    // Keep only the children that belong to this iteration of the parent.
    return parentPath === ownPath
  })
})

const hasChildren = computed(() => childNodeHistories.value.length > 0)

/**
 * Return an array of objects with keys: iteration and histories.
 *
 * iteration: the run number of the current node run.
 * histories: the child node histories for that run.
 *
 * This is used to group child node histories by run, so that we can show
 * Run 1, Run 2, etc and the correct child histories for each run.
 */
const childNodeHistoriesByIteration = computed(() => {
  const iterationsHistories = {}
  for (const childHistory of childNodeHistories.value) {
    const iteration = childHistory.iteration ?? 0
    if (!iterationsHistories[iteration]) iterationsHistories[iteration] = []
    iterationsHistories[iteration].push(childHistory)
  }
  return Object.entries(iterationsHistories)
    .sort((a, b) => Number(a[0]) - Number(b[0]))
    .map(([iteration, histories]) => ({
      iteration: Number(iteration),
      histories,
    }))
})

const openNodeResultButtonContext = () => {
  if (nodeResultButtonContext.value && nodeResultButtonContextToggle.value) {
    nodeResultButtonContext.value.toggle(
      nodeResultButtonContextToggle.value,
      'bottom',
      'left',
      0
    )
  }
}

const showNodeResultModal = async () => {
  fetchingResult.value = true
  try {
    const nodeHistoryId = props.nodeHistory.id
    await store.dispatch('automationHistory/fetchNodeResult', {
      nodeHistoryId,
    })
    let result = store.getters['automationHistory/getNodeResult'](nodeHistoryId)
    if (result?._error) {
      result = result._error
    } else if (nodeType.value.returnsList && result?.results) {
      result = result.results
    }
    resolvedSampleData.value = result
    nodeResultModal.value.show()
  } catch (error) {
    notifyIf(error)
  } finally {
    fetchingResult.value = false
  }
}
</script>
