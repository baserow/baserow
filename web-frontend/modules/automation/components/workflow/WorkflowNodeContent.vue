<template>
  <div
    class="workflow-node-content"
    :class="{
      'workflow-node-content--selected': selected,
      'workflow-node-content--dragging': isDragging,
      'workflow-node-content--utility': nodeType.isUtilityNode,
    }"
    :title="!isInError ? displayLabel : ''"
    :data-before-label="getDataBeforeLabel"
    :draggable="isDraggable"
    @dragstart="handleDragStart"
    @dragend="handleDragEnd"
    @mousedown.stop
    @click="emit('select-node', node)"
  >
    <div v-if="isDraggable" class="workflow-node-content__drag-handle"></div>
    <div class="workflow-node-content__icon">
      <i
        v-if="nodeType.iconClass"
        :class="{
          loading: loading,
          'iconoir-hammer': !loading && !isInteractionReady,
          [nodeType.iconClass]: !loading && isInteractionReady,
        }"
      ></i>
      <img v-else :alt="nodeType.name" :src="nodeType.image" />
    </div>

    <h1 class="workflow-node-content__title">{{ displayLabel }}</h1>

    <Badge
      v-if="isInteractionReady && isInError"
      :key="errorMessage"
      v-tooltip="errorMessage"
      rounded
      color="yellow"
      size="large"
    >
      {{ $t('workflowNode.actionConfigure') }}
    </Badge>

    <div
      v-if="isInteractionReady"
      class="workflow-node-content__more--wrapper"
      draggable="false"
      @mousedown.prevent
    >
      <a
        ref="editNodeContextToggle"
        role="button"
        :title="$t('workflowNode.nodeOptions')"
        class="workflow-node-content__more-icon"
        @click="openEditContext()"
      >
        <i class="baserow-icon-more-vertical"></i>
      </a>
    </div>

    <Context
      ref="editNodeContext"
      overflow-scroll
      max-height-if-outside-viewport
    >
      <div class="context__menu-title">
        {{ nodeType.getDefaultLabel({ automation, node }) }} ({{ node.id }})
      </div>
      <ul class="context__menu">
        <li class="context__menu-item">
          <a
            :key="getReplaceErrorMessage"
            v-tooltip="getReplaceErrorMessage || null"
            role="button"
            class="context__menu-item-link context__menu-item-link--switch"
            :class="{ disabled: getReplaceErrorMessage }"
            @click="!getReplaceErrorMessage && openReplaceContext()"
          >
            <i class="context__menu-item-icon baserow-icon-history"></i>
            {{ $t('workflowNode.moreReplace') }}
          </a>
        </li>
        <li v-if="canBeDuplicated" class="context__menu-item">
          <a
            role="button"
            class="context__menu-item-link"
            @click="emit('duplicate-node', node.id)"
          >
            <i class="context__menu-item-icon iconoir-copy"></i>
            {{ $t('workflowNode.moreDuplicate') }}
          </a>
        </li>
        <li class="context__menu-item context__menu-item--with-separator">
          <a
            :key="getDeleteErrorMessage"
            v-tooltip="getDeleteErrorMessage || null"
            role="button"
            class="context__menu-item-link context__menu-item-link--delete"
            :class="{ disabled: getDeleteErrorMessage }"
            @click="!getDeleteErrorMessage && emit('remove-node', node.id)"
          >
            <i class="context__menu-item-icon iconoir-bin"></i>
            {{ $t('workflowNode.actionDelete') }}
          </a>
        </li>
      </ul>
    </Context>
    <WorkflowNodeContext
      ref="replaceNodeContext"
      :node="node"
      :only-trigger="nodeType.isTrigger"
      @change="emit('replace-node', { node: node, type: $event })"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useVueFlow } from '@vue2-flow/core'
import { useStore, useContext, inject, computed } from '@nuxtjs/composition-api'
import WorkflowNodeContext from '@baserow/modules/automation/components/workflow/WorkflowNodeContext'
import flushPromises from 'flush-promises'
import NodeGraphHandler from '@baserow/modules/automation/utils/nodeGraphHandler'

const { onMove } = useVueFlow()
const props = defineProps({
  node: {
    type: Object,
    required: true,
  },
  selected: {
    type: Boolean,
    default: false,
  },
  dragging: {
    type: Boolean,
    default: false,
  },
  debug: {
    type: Boolean,
    default: false,
  },
  readOnly: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'remove-node',
  'replace-node',
  'select-node',
  'duplicate-node',
])

const isDragging = ref(false)

/**
 * When the pane is moved, if we have an active node context (whether it is
 * the edit, or replace context), we hide it. This is to ensure that the
 * context menu does not stay open when the user interacts with the workflow.
 */
const activeNodeContext = ref(null)
onMove(() => {
  activeNodeContext.value?.hide()
})

const editNodeContext = ref(null)
const editNodeContextToggle = ref(null)
const openEditContext = () => {
  if (editNodeContext.value && editNodeContextToggle.value) {
    activeNodeContext.value = editNodeContext
    editNodeContext.value.toggle(
      editNodeContextToggle.value,
      'bottom',
      'left',
      0
    )
  }
}

const replaceNodeContext = ref(null)
const openReplaceContext = async () => {
  editNodeContext.value.hide()
  // As the target isn't the element that triggered the show of the context it is not
  // ignored by the click outside handler and it immediately closes the context
  await flushPromises()
  activeNodeContext.value = replaceNodeContext
  replaceNodeContext.value.toggle(
    editNodeContextToggle.value,
    'bottom',
    'left',
    0
  )
}

const store = useStore()
const { app } = useContext()
const workflow = inject('workflow')
const automation = inject('automation')

const nodeType = computed(() => {
  return app.$registry.get('node', props.node.type)
})

const isDraggable = computed(() => {
  return !nodeType.value.isFixed
})

const handleDragStart = (event) => {
  isDragging.value = true
  store.dispatch('automationWorkflowNode/setDraggingNodeId', props.node.id)
}

const handleDragEnd = () => {
  isDragging.value = false
  store.dispatch('automationWorkflowNode/setDraggingNodeId', null)
}

const loading = computed(() => {
  return store.getters['automationWorkflowNode/getLoading'](props.node)
})
const isInError = computed(() => {
  return nodeType.value.isInError({ service: props.node.service })
})

/**
 * This computed property retrieves the error message associated with
 * the node if it is in an error state.
 * @type {string} - The error message for the node.
 */
const errorMessage = computed(() => {
  return nodeType.value.getErrorMessage({
    service: props.node.service,
    node: props.node,
  })
})

/**
 * This computed property checks if the node is ready for interaction.
 * A node is considered ready if it is not in read-only mode and not in
 * debug mode (i.e. it is not being debugged).
 * @type {bool} - Indicates whether the node is ready for interaction.
 */
const isInteractionReady = computed(() => {
  return !props.readOnly && !props.debug
})

/**
 * This computed property returns the label that should be displayed
 * for this node. If the node is in debug mode, it will return a debug
 * label that includes the node ID, previous node ID, and output UID.
 * Otherwise, it will return the label passed in through props.
 * Useful for debugging purposes to quickly identify nodes in the workflow.
 * @type {string} - The label to display for the node.
 */
const displayLabel = computed(() => {
  return props.debug
    ? `ID: ${props.node.id}`
    : nodeType.value.getLabel({
        automation: automation.value,
        node: props.node,
      })
})

/**
 * If this node's type finds that in its current state, it cannot
 * be replaced with a different node type, this computed property
 * will return a human-friendly error message.
 * @type {string} - A human-friendly error message.
 */
const getReplaceErrorMessage = computed(() => {
  return nodeType.value.getReplaceErrorMessage({
    workflow: workflow.value,
    node: props.node,
  })
})

/**
 * If this node's type finds that in its current state, it cannot be deleted,
 * this computed property will return a human-friendly error message.
 * @type {string} - A human-friendly error message.
 */
const getDeleteErrorMessage = computed(() => {
  return nodeType.value.getDeleteErrorMessage({
    workflow: workflow.value,
    node: props.node,
  })
})

/**
 * This computed property determines the label that should be displayed
 * before the node label in the workflow editor.
 * @returns {string} - The label to display before the node.
 */
const getDataBeforeLabel = computed(() => {
  const [referenceNode, position, output] = new NodeGraphHandler(
    workflow.value
  ).getNodePosition(props.node)

  if (referenceNode === null) {
    return app.i18n.t('workflowNode.beforeLabelTrigger')
  }
  const referenceNodeType = app.$registry.get('node', referenceNode.type)
  return referenceNodeType.getBeforeLabel({
    workflow: workflow.value,
    node: referenceNode,
    position,
    output,
  })
})

const canBeDuplicated = computed(() => {
  return nodeType.value.isDuplicable({
    workflow: workflow.value,
    node: props.node,
  })
})
</script>
