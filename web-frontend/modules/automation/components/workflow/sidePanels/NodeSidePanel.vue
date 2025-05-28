<template>
  <ReadOnlyForm
    v-if="node"
    :read-only="!$hasPermission('automation.node.update', node, workspace.id)"
  >
    <FormGroup required :label="$t('nodeSidePanel.action')">
      <Dropdown
        v-model="node.type"
        class="dropdown--floating margin-top-2"
        :fixed-items="true"
      >
        <DropdownItem
          v-for="siblingNodeType in siblingNodeTypes"
          :key="siblingNodeType.getType()"
          :name="siblingNodeType.name"
          :value="siblingNodeType.getType()"
          :description="siblingNodeType.description"
        />
      </Dropdown>
    </FormGroup>
    <hr class="margin-bottom-3 margin-top-3" />
    <FormGroup required :label="$t('nodeSidePanel.details')">
      <component
        :is="nodeType.formComponent"
        :key="node.id"
        :node="node"
        class="node-form margin-top-2"
        @values-changed="handleNodeServiceChange"
      />
    </FormGroup>
  </ReadOnlyForm>
</template>

<script setup>
import { inject, useStore, useContext, computed } from '@nuxtjs/composition-api'
import ReadOnlyForm from '@baserow/modules/core/components/ReadOnlyForm'

const store = useStore()
const { app } = useContext()

const workspace = inject('workspace')
const currentWorkflow = inject('currentWorkflow')

const node = computed(() => {
  return store.getters['automationWorkflowNode/getSelected'](
    currentWorkflow.value
  )
})
const nodeType = computed(() => {
  return app.$registry.get('node', node.value.type)
})

const handleNodeServiceChange = (newServiceChanges) => {
  const updatedNode = { ...node.value }
  updatedNode.service = { ...updatedNode.service, ...newServiceChanges }
  store.dispatch('automationWorkflowNode/update', {
    workflow: currentWorkflow.value,
    nodeId: updatedNode.id,
    values: updatedNode,
  })
}

const nodeTypes = computed(() => app.$registry.getOrderedList('node'))
const siblingNodeTypes = computed(() =>
  nodeTypes.value.filter(
    (type) =>
      type.isWorkflowTrigger === nodeType.value.isWorkflowTrigger &&
      type.isWorkflowAction === nodeType.value.isWorkflowAction
  )
)
</script>
