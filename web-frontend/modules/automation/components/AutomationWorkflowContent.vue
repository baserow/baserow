<template>
  <div class="automation-workflow">
    <AutomationHeader
      :automation="automation"
      @debug-toggled="handleDebugToggle"
    />
    <div
      class="layout__col-2-2 automation-workflow__content"
      :class="{ 'automation-workflow__content--loading': loading }"
    >
      <div v-if="loading" />
      <div
        v-else
        class="automation-workflow__editor"
        data-highlight="automation-editor"
      >
        <client-only>
          <WorkflowEditor
            v-model="selectedNodeId"
            :nodes="workflowNodes"
            :read-only="isReadOnly"
            :is-adding-node="isAddingNode"
            @add-node="handleAddNode"
            @remove-node="handleRemoveNode"
            @replace-node="handleReplaceNode"
            @move-node="handleMoveNode"
            @duplicate-node="handleDuplicateNode"
          />
        </client-only>
      </div>
      <div v-if="activeSidePanel" class="automation-workflow__side-panel">
        <EditorSidePanels
          :active-side-panel="activeSidePanel"
          :data-highlight="activeSidePanelType?.guidedTourAttr"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, provide } from 'vue'

import AutomationHeader from '@baserow/modules/automation/components/AutomationHeader'
import WorkflowEditor from '@baserow/modules/automation/components/workflow/WorkflowEditor'
import EditorSidePanels from '@baserow/modules/automation/components/workflow/EditorSidePanels'
import { notifyIf } from '@baserow/modules/core/utils/error'

const props = defineProps({
  workspace: {
    type: Object,
    required: true,
  },
  automation: {
    type: Object,
    required: true,
  },
  workflow: {
    type: Object,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const { $store, $registry, $hasPermission } = useNuxtApp()

// Local state
const isAddingNode = ref(false)
const workflowDebug = ref(false)

// Computed properties
const isDev = computed(() => import.meta.env.MODE === 'development')

const workflowNodes = computed(() => {
  if (!props.workflow?.nodes) {
    return []
  }
  return $store.getters['automationWorkflowNode/getNodes'](props.workflow)
})

const activeSidePanel = computed(() => {
  return $store.getters['automationWorkflow/getActiveSidePanel']
})

const activeSidePanelType = computed(() => {
  return activeSidePanel.value
    ? $registry.get('editorSidePanel', activeSidePanel.value)
    : null
})

const selectedNodeId = computed({
  get() {
    return props.workflow ? props.workflow.selectedNodeId : null
  },
  set(nodeId) {
    let nodeToSelect = null
    if (nodeId) {
      nodeToSelect = $store.getters['automationWorkflowNode/findById'](
        props.workflow,
        nodeId
      )
    }
    $store.dispatch('automationWorkflowNode/select', {
      workflow: props.workflow,
      node: nodeToSelect,
    })
  },
})

// Provide values for child components
provide(
  'workspace',
  computed(() => props.workspace)
)
provide(
  'automation',
  computed(() => props.automation)
)
provide(
  'workflow',
  computed(() => props.workflow)
)

provide('isDev', isDev)
provide('workflowDebug', workflowDebug)

const isReadOnly = computed(
  () =>
    !$hasPermission('application.update', props.automation, props.workspace.id)
)

// Methods
function handleDebugToggle(newDebugState) {
  workflowDebug.value = newDebugState
}

async function handleAddNode({ type, referenceNode, position, output }) {
  try {
    isAddingNode.value = true
    await $store.dispatch('automationWorkflowNode/create', {
      workflow: props.workflow,
      type,
      referenceNode,
      position,
      output,
    })
  } catch (err) {
    notifyIf(err, 'automation')
  } finally {
    isAddingNode.value = false
  }
}

async function handleRemoveNode(nodeId) {
  if (!props.workflow) {
    return
  }
  try {
    await $store.dispatch('automationWorkflowNode/delete', {
      workflow: props.workflow,
      nodeId: parseInt(nodeId),
    })
  } catch (err) {
    notifyIf(err, 'automation')
  }
}

async function handleReplaceNode({ node, type }) {
  try {
    await $store.dispatch('automationWorkflowNode/replace', {
      workflow: props.workflow,
      nodeId: parseInt(node.id),
      newType: type,
    })
  } catch (err) {
    notifyIf(err, 'automation')
  }
}

async function handleMoveNode(moveData) {
  const movedNodeId = $store.getters['automationWorkflowNode/getDraggingNodeId']

  $store.dispatch('automationWorkflowNode/setDraggingNodeId', null)

  if (!movedNodeId) {
    return
  }
  try {
    await $store.dispatch('automationWorkflowNode/move', {
      workflow: props.workflow,
      moveData: {
        movedNodeId,
        ...moveData,
      },
    })
  } catch (err) {
    notifyIf(err, 'automation')
  }
}

async function handleDuplicateNode(nodeId) {
  await $store.dispatch('automationWorkflowNode/duplicate', {
    workflow: props.workflow,
    nodeId,
  })
}
</script>
