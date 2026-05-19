<template>
  <div
    class="node-history__header"
    :style="depth > 0 ? { marginLeft: '24px' } : {}"
  >
    <Expandable
      v-if="nodeHistory.is_container"
      toggle-on-click
      @toggle="onToggle"
    >
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
        <div
          v-if="childEntry.status === STATUS_LOADING"
          class="node-history__loading"
          :style="{ marginLeft: '48px' }"
        >
          <div class="loading"></div>
        </div>
        <div
          v-else-if="childEntry.status === STATUS_ERROR"
          class="node-history__error-info"
          :style="{ marginLeft: '48px' }"
        >
          {{ $t('historySidePanel.failedToLoad') }}
        </div>
        <Expandable
          v-for="group in childNodeHistoriesByIteration"
          v-else
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
                  v-for="childNodeHistory in group.histories"
                  :key="childNodeHistory.id"
                  :workflow-history-id="workflowHistoryId"
                  :node-history="childNodeHistory"
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

    <Context v-if="!nodeHistory.is_container" ref="nodeResultButtonContext">
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
      v-if="!nodeHistory.is_container"
      ref="nodeResultModal"
      :sample-data="resolvedSampleData"
      :title="nodeTypeLabel"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useStore } from 'vuex'

import SampleDataModal from '@baserow/modules/automation/components/sidebar/SampleDataModal'
import { notifyIf } from '@baserow/modules/core/utils/error'
import {
  STATUS_ERROR,
  STATUS_LOADED,
  STATUS_LOADING,
} from '@baserow/modules/automation/constants'

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

const nodeTypeLabel = computed(() => {
  return props.nodeHistory.node_label || nodeType.value.name
})

const childEntry = computed(() =>
  store.getters['automationHistory/getNodeHistoriesByParent'](
    props.workflowHistoryId,
    props.nodeHistory.node,
    props.nodeHistory.iteration_path
  )
)

const onToggle = () => {
  if (!props.nodeHistory.is_container) return
  store.dispatch('automationHistory/fetchNodeHistories', {
    workflowHistoryId: props.workflowHistoryId,
    parentNodeId: props.nodeHistory.node,
    iterationPath: props.nodeHistory.iteration_path,
  })
}

const iterationHasError = (group) => {
  return group.histories.some(
    (h) => h.status === 'error' || h.has_error_descendant
  )
}

const hasOwnError = computed(() => props.nodeHistory.status === 'error')

const status = computed(() => {
  return hasOwnError.value || props.nodeHistory.has_error_descendant
    ? 'error'
    : 'success'
})

const statusLabel = computed(() => {
  return status.value === 'success'
    ? app.$i18n.t('historySidePanel.statusSuccessBadge')
    : app.$i18n.t('historySidePanel.statusErrorBadge')
})

const errorMessage = computed(() => props.nodeHistory.message)

/**
 * Return an array of objects with keys: iteration and histories.
 *
 * iteration: the run number of the current node run.
 * histories: the child node histories for that run.
 *
 * Group the fetched child node histories by iteration so the UI can render
 * "Run 1", "Run 2", etc.
 */
const childNodeHistoriesByIteration = computed(() => {
  const iterationsHistories = {}
  for (const childHistory of childEntry.value.items) {
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
    await store.dispatch('automationHistory/fetchNodeResult', {
      nodeHistoryId: props.nodeHistory.id,
    })
    const entry = store.getters['automationHistory/getNodeResult'](
      props.nodeHistory.id
    )
    if (entry.status !== STATUS_LOADED) return
    let result = entry.result
    if (result?._error) {
      result = result._error
    } else if (nodeType.value.serviceType.returnsList && result?.results) {
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
