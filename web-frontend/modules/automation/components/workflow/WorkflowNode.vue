<template>
  <div
    class="workflow-editor__node"
    :data-before-label="
      props.data.isTrigger
        ? $t('workflowNode.beforeLabelTrigger')
        : $t('workflowNode.beforeLabelAction')
    "
  >
    <div class="workflow-editor__node-icon">
      <i :class="loading ? 'loading' : nodeType.iconClass"></i>
    </div>

    <h1 class="workflow-editor__node-title">{{ props.label }}</h1>

    <Badge v-if="isInError" rounded color="yellow" size="large">
      {{ $t('workflowNode.actionConfigure') }}</Badge
    >
    <div
      v-if="!props.data.readOnly"
      class="workflow-editor__node-more--wrapper"
    >
      <a
        v-if="!props.data.isTrigger"
        ref="editNodeContextToggle"
        role="button"
        title="Node options"
        class="workflow-editor__node-more-icon"
        @click="openEditContext()"
      >
        <i class="baserow-icon-more-vertical"></i>
      </a>
      <a
        ref="replaceNodeContextToggle"
        role="button"
        :title="$t('workflowNode.moreReplace')"
        class="workflow-editor__node-more-icon"
        @click="openReplaceContext()"
      >
        <i class="baserow-icon-history"></i>
      </a>
    </div>

    <Context
      ref="editNodeContext"
      overflow-scroll
      max-height-if-outside-viewport
    >
      <div class="context__menu-title">
        {{ label }} ({{ props.data.nodeId }})
      </div>
      <ul class="context__menu">
        <li class="context__menu-item">
          <a
            role="button"
            class="context__menu-item-link context__menu-item-link--delete"
            @click="emit('remove-node', props.id)"
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
const replaceNodeContextToggle = ref(null)
const openReplaceContext = () => {
  if (replaceNodeContext.value && replaceNodeContextToggle.value) {
    activeNodeContext.value = replaceNodeContext
    replaceNodeContext.value.toggle(
      replaceNodeContextToggle.value,
      'bottom',
      'left',
      0
    )
  }
}

const store = useStore()
const { app } = useContext()
const workflow = inject('workflow')
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
