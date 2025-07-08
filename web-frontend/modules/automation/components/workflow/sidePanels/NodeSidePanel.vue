<template>
  <ReadOnlyForm
    v-if="node"
    :read-only="
      workflowReadOnly ||
      !$hasPermission('automation.node.update', node, workspace.id)
    "
  >
    <component
      :is="nodeType.formComponent"
      :key="node.id"
      small
      :loading="nodeLoading"
      :service="node.service"
      :application="automation"
      enable-integration-picker
      :default-values="node.service"
      class="margin-top-2"
      @values-changed="handleNodeServiceChange"
    />
  </ReadOnlyForm>
</template>

<script setup>
import {
  inject,
  provide,
  useStore,
  useContext,
  computed,
} from '@nuxtjs/composition-api'
import { reactive } from 'vue'
import ReadOnlyForm from '@baserow/modules/core/components/ReadOnlyForm'
import AutomationBuilderFormulaInput from '@baserow/modules/automation/components/AutomationBuilderFormulaInput'
import { DATA_PROVIDERS_ALLOWED_NODE_ACTIONS } from '@baserow/modules/automation/enums'
import _ from 'lodash'

const store = useStore()
const { app } = useContext()

provide('formulaComponent', AutomationBuilderFormulaInput)
provide('dataProvidersAllowed', DATA_PROVIDERS_ALLOWED_NODE_ACTIONS)

const workspace = inject('workspace')
const automation = inject('automation')
const workflow = inject('workflow')
const workflowReadOnly = inject('workflowReadOnly')

const node = computed(() => {
  return store.getters['automationWorkflowNode/getSelected'](workflow.value)
})

/**
 * The application context is provided as a reactive object
 * as the `node` (the selected node) will change. If it's not
 * reactive, the components that consume this context will not
 * update when the node changes.
 */
const applicationContext = reactive({
  get node() {
    return node.value
  },
  get automation() {
    return automation.value
  },
  get workflow() {
    return workflow.value
  },
})
provide('applicationContext', applicationContext)

const nodeType = computed(() => {
  return app.$registry.get('node', node.value.type)
})

const handleNodeServiceChange = async (newServiceChanges) => {
  const differences = Object.fromEntries(
    Object.entries(newServiceChanges).filter(
      ([key, value]) => !_.isEqual(value, node.value.service[key])
    )
  )
  if (Object.keys(differences).length === 0) {
    // Nothing has changed.
    return
  }
  const updatedNode = { ...node.value }
  updatedNode.service = { ...updatedNode.service, ...differences }
  await store.dispatch('automationWorkflowNode/updateDebounced', {
    workflow: workflow.value,
    node: node.value,
    values: updatedNode,
  })
}

const nodeLoading = computed(() => {
  return store.getters['automationWorkflowNode/getLoading'](node.value)
})
</script>
