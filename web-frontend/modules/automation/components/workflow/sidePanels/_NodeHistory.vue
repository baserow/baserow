<template>
  <div
    class="node-history__container"
    :style="nodeDepth > 0 ? { marginLeft: nodeDepth * 24 + 'px' } : {}"
  >
    <div class="node-history">
      <div class="node-history__icon">
        <i :class="getNodeIconClass(nodeHistory.node)"></i>
      </div>

      <div class="node-history__info">
        <div
          class="node-history__info-type"
          :class="{
            'node-history__info-type-error': nodeHistory.status === 'error',
          }"
        >
          {{ nodeTypeLabel(nodeHistory.node) }}
        </div>
      </div>

      <div class="node-history__badge">
        <Badge
          :key="nodeHistory.node"
          rounded
          :color="nodeHistory.status === 'error' ? 'red' : 'green'"
          size="small"
        >
          {{ nodeHistoryStatus(nodeHistory.status) }}
        </Badge>
      </div>
    </div>

    <div v-if="nodeHistory.status === 'error'" class="node-history__error">
      <div class="node-history__error-info">
        {{ nodeHistory.message }}
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

            <div class="node-history__error-expand-icon">
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
            {{ nodeHistory.message }}
          </div>
        </template>
      </Expandable>
    </div>
  </div>
</template>

<script setup>
import { useStore } from 'vuex'

const app = useNuxtApp()

const props = defineProps({
  nodeHistory: {
    type: Object,
    required: true,
  },
  nodeDepth: {
    type: Number,
    default: 0,
  },
})

const store = useStore()
const workflow = inject('workflow')
const automation = inject('automation')

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
  return nodeType.getLabel({
    automation: automation.value,
    node: node,
  })
}

const nodeHistoryStatus = (status) => {
  switch (status) {
    case 'success':
      return app.$i18n.t('historySidePanel.statusSuccessBadge')
    case 'error':
      return app.$i18n.t('historySidePanel.statusErrorBadge')
    default:
      return app.$i18n.t('historySidePanel.statusErrorBadge')
  }
}
</script>
