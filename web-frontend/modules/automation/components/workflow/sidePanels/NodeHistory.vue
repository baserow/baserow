<template>
  <div
    class="node-history__header"
    :style="depth > 0 ? { marginLeft: '24px' } : {}"
  >
    <Expandable v-if="hasChildren" toggle-on-click>
      <template #header="{ expanded }">
        <div class="node-history__header-row">
          <div class="node-history__header-icon">
            <i :class="nodeIconClass"></i>
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
                  v-for="nodeHistory in group.histories"
                  :key="nodeHistory.id"
                  :node-id="nodeHistory.node"
                  :node-histories="[nodeHistory]"
                  :child-node-histories-by-parent="childNodeHistoriesByParent"
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
        <i :class="nodeIconClass"></i>
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
        icon="iconoir-code-brackets node-history__show-result-button-icon"
        @click="showNodeResultModal"
      >
        {{ $t('historySidePanel.showResult') }}
      </Button>
    </Context>

    <SampleDataModal
      v-if="!hasChildren"
      ref="nodeResultModal"
      :sample-data="nodeResultData"
      :title="nodeTypeLabel"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'

import SampleDataModal from '@baserow/modules/automation/components/sidebar/SampleDataModal'

const app = useNuxtApp()

const props = defineProps({
  nodeId: {
    type: Number,
    required: true,
  },
  nodeHistories: {
    type: Array,
    default: () => [],
  },
  childNodeHistoriesByParent: {
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

const nodeType = computed(() => {
  return app.$registry.get('node', props.nodeHistories[0].node_type)
})

const nodeIconClass = computed(() => {
  return nodeType.value.iconClass
})

const nodeTypeLabel = computed(() => {
  const nodeHistory = props.nodeHistories[0]
  const baseLabel = nodeHistory.node_label || nodeType.value.name
  const result = nodeHistory.result
  if (result.edge) {
    // Show which branch was taken.
    return `${baseLabel} (${result.edge?.label || app.$i18n.t('nodeType.defaultEdgeLabelFallback')})`
  }
  return baseLabel
})

const nodeResultData = computed(() => {
  // Since the SampleDataModal is only shown for final nodes (not nodes with
  // children), the history will only ever have just one result.
  const result = props.nodeHistories[0].result

  if (result?._error) {
    return result._error
  }
  if (nodeType.value.serviceType.returnsList && result?.results) {
    return result.results
  }
  return result
})

const hasDescendantError = (nodeId) => {
  const children = props.childNodeHistoriesByParent[nodeId] || []
  return children.some(
    (child) => child.status === 'error' || hasDescendantError(child.node)
  )
}

const iterationHasError = (group) => {
  return group.histories.some(
    (h) => h.status === 'error' || hasDescendantError(h.node)
  )
}

const hasOwnError = computed(() =>
  props.nodeHistories.some((nh) => nh.status === 'error')
)

const status = computed(() => {
  if (props.nodeHistories.length === 0) return 'success'

  const childError = hasDescendantError(props.nodeId)
  return hasOwnError.value || childError ? 'error' : 'success'
})

const statusLabel = computed(() => {
  return status.value === 'success'
    ? app.$i18n.t('historySidePanel.statusSuccessBadge')
    : app.$i18n.t('historySidePanel.statusErrorBadge')
})

const errorMessage = computed(() => {
  const historyWithError = props.nodeHistories.find(
    (nh) => nh.status === 'error'
  )
  return historyWithError.message
})

const childNodeHistories = computed(
  () => props.childNodeHistoriesByParent[props.nodeId] || []
)

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

const showNodeResultModal = () => {
  nodeResultModal.value.show()
}
</script>
