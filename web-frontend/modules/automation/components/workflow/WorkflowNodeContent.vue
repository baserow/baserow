<template>
  <div
    class="workflow-node-content__wrapper"
    @click="emit('select-node', node)"
  >
    <div
      class="workflow-node-content"
      :class="{
        'workflow-node-content--selected': selected,
      }"
      :title="displayLabel"
      :data-before-label="getDataBeforeLabel"
    >
      <div class="workflow-node-content__icon">
        <i
          :class="{
            loading: loading,
            'iconoir-hammer': !loading && !isInteractionReady,
            [nodeType.iconClass]: !loading && isInteractionReady,
          }"
        ></i>
      </div>

      <h1 class="workflow-node-content__title">{{ displayLabel }}</h1>

      <Badge
        v-if="isInteractionReady && isInError"
        rounded
        color="yellow"
        size="large"
      >
        {{ $t('workflowNode.actionConfigure') }}
      </Badge>

      <div
        v-if="isInteractionReady"
        class="workflow-node-content__more--wrapper"
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
          <li class="context__menu-item">
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
        @change="emit('replace-node', { node: node, type: $event })"
      />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useVueFlow } from '@vue2-flow/core'
import { useStore, useContext, inject, computed } from '@nuxtjs/composition-api'
import WorkflowNodeContext from '@baserow/modules/automation/components/workflow/WorkflowNodeContext'
import flushPromises from 'flush-promises'
import { CoreRouterNodeType } from '@baserow/modules/automation/nodeTypes'

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

const emit = defineEmits(['remove-node', 'replace-node', 'select-node'])

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
const loading = computed(() => {
  return store.getters['automationWorkflowNode/getLoading'](props.node)
})
const isInError = computed(() => {
  return nodeType.value.isInError({ service: props.node.service })
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
    ? app.i18n.t('workflowNode.displayLabelDebug', {
        id: props.node.id,
        previousNodeId: props.node.previous_node_id || 'none',
        outputUid: props.node.previous_node_output || 'none',
      })
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
 * before the node label in the workflow editor. It checks the previous node
 * in the workflow to determine if it is a router node or if the current node
 * is an output node. Based on these conditions, it returns the appropriate
 * label for the node.
 * @returns {string} - The label to display before the node label.
 */
const getDataBeforeLabel = computed(() => {
  const previousNode = store.getters['automationWorkflowNode/getPreviousNode'](
    workflow.value,
    props.node
  )
  // TODO use a generic way to handle that not specific to router node
  const previousNodeIsRouter =
    previousNode?.type === CoreRouterNodeType.getType()
  const isOutputNode = props.node.previous_node_output.length > 0
  switch (true) {
    case nodeType.value.isTrigger:
      return app.i18n.t('workflowNode.beforeLabelTrigger')
    case isOutputNode:
      return app.i18n.t('workflowNode.beforeLabelCondition')
    case previousNodeIsRouter && !isOutputNode:
      return app.i18n.t('workflowNode.beforeLabelConditionDefault')
    default:
      return app.i18n.t('workflowNode.beforeLabelAction')
  }
})
</script>
