<template>
  <div
    class="workflow-editor__node"
    :data-before-label="
      data.isTrigger
        ? $t('workflowNode.beforeLabelTrigger')
        : $t('workflowNode.beforeLabelAction')
    "
  >
    <div class="workflow-editor__node-icon">
      <i :class="loading ? 'loading' : nodeType.iconClass"></i>
    </div>

    <h1 class="workflow-editor__node-title">{{ label }}</h1>

    <Badge v-if="isInError" rounded color="yellow" size="large">
      {{ $t('workflowNode.actionConfigure') }}</Badge
    >
    <div v-if="!data.readOnly" class="workflow-editor__node-more--wrapper">
      <a
        ref="editNodeContextToggle"
        role="button"
        title="Node options"
        class="workflow-editor__node-more-icon"
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
        {{ nodeType.getDefaultLabel({ automation, node }) }} ({{ data.nodeId }})
      </div>
      <ul class="context__menu">
        <li class="context__menu-item">
          <a
            role="button"
            class="context__menu-item-link context__menu-item-link--switch"
            @click="openReplaceContext()"
          >
            <i class="context__menu-item-icon baserow-icon-history"></i>
            {{ $t('workflowNode.moreReplace') }}
          </a>
        </li>
        <li v-if="!data.isTrigger" class="context__menu-item">
          <a
            role="button"
            class="context__menu-item-link context__menu-item-link--delete"
            @click="emit('remove-node', id)"
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
      @change="handleReplaceNode"
    ></WorkflowNodeContext>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useVueFlow } from '@vue2-flow/core'
import { useStore, useContext, inject, computed } from '@nuxtjs/composition-api'
import WorkflowNodeContext from '@baserow/modules/automation/components/workflow/WorkflowNodeContext'
import flushPromises from 'flush-promises'

const { onMove } = useVueFlow()
const props = defineProps({
  id: {
    type: String,
    default: null,
  },
  label: {
    type: String,
    default: null,
  },
  selected: {
    type: Boolean,
    default: false,
  },
  dragging: {
    type: Boolean,
    default: false,
  },
  data: {
    type: Object,
    default: () => ({ nodeId: null, readOnly: false }),
  },
})

const emit = defineEmits(['remove-node', 'replace-node'])

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
const node = computed(() => {
  return store.getters['automationWorkflowNode/findById'](
    workflow.value,
    props.id
  )
})
const nodeType = computed(() => {
  return app.$registry.get('node', node.value.type)
})
const loading = computed(() => {
  return store.getters['automationWorkflowNode/getLoading'](node.value)
})
const isInError = computed(() => {
  return nodeType.value.isInError({ service: node.value.service })
})

const handleReplaceNode = (newType) => {
  emit('replace-node', props.id, newType)
}
</script>
