<template>
  <div
    class="node-history__header"
    :style="depth > 0 ? { marginLeft: '24px' } : {}"
  >
    <Expandable v-if="hasChildren" toggle-on-click>
      <template #header="{ expanded }">
        <div class="node-history__header-row">
          <div class="node-history__header-icon">
            <i :class="getNodeIconClass(nodeId)"></i>
          </div>
          <div class="node-history__header-info">
            <div>
              <div
                class="node-history__header-info-type"
                :class="{
                  'node-history__header-info-type-error': status === 'error',
                }"
              >
                n{{ nodeId }} - {{ nodeTypeLabel(nodeId) }}
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
                <span class="node-history__header-info-type">
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
        <i :class="getNodeIconClass(nodeId)"></i>
      </div>
      <div class="node-history__header-info">
        <div
          class="node-history__header-info-type"
          :class="{
            'node-history__header-info-type-error': status === 'error',
          }"
        >
          n{{ nodeId }} - {{ nodeTypeLabel(nodeId) }}
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

    <div v-if="status === 'error'" class="node-history__error">
      <div class="node-history__error-info">
        {{ nodeHistories[0].message }}
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
            {{ nodeHistories[0].message }}
          </div>
        </template>
      </Expandable>
    </div>

    <!-- TODO: find a better way to show button pop-up to avoid background overlap. -->
    <Context ref="nodeResultButtonContext">
      <Button
        ref="nodeResultContextToggle"
        type="secondary"
        full-width
        icon="iconoir-code-brackets node-history__show-result-button-icon"
        @click="showNodeResultModal"
      >
        Show Result
      </Button>
    </Context>

    <SampleDataModal
      ref="nodeResultModal"
      :sample-data="nodeHistories[0].result"
      :title="nodeTypeLabel(nodeId)"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useStore } from 'vuex'

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

const store = useStore()
const workflow = inject('workflow')
const automation = inject('automation')

const nodeResultButtonContext = ref(null)
const nodeResultButtonContextToggle = ref(null)
const nodeResultModal = ref(null)

const getNode = (nodeId) => {
  return store.getters['automationWorkflowNode/findById'](
    workflow.value,
    nodeId
  )
}

const getNodeType = (nodeId) => {
  return app.$registry.get('node', getNode(nodeId).type)
}

const getNodeIconClass = (nodeId) => {
  const nodeType = getNodeType(nodeId)
  return nodeType.iconClass
}

const nodeTypeLabel = (nodeId) => {
  const nodeType = getNodeType(nodeId)
  const node = getNode(nodeId)
  return nodeType.getLabel({ automation: automation.value, node })
}

const status = computed(() => {
  if (props.nodeHistories.length === 0) return 'success'
  return props.nodeHistories.some(
    (nodeHistory) => nodeHistory.status === 'error'
  )
    ? 'error'
    : 'success'
})

const statusLabel = computed(() => {
  if (status.value === 'error') {
    return app.$i18n.t('historySidePanel.statusErrorBadge')
  }
  if (status.value === 'success') {
    return app.$i18n.t('historySidePanel.statusSuccessBadge')
  }
  return app.$i18n.t('historySidePanel.statusErrorBadge')
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
