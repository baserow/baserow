<template>
  <aside class="side-panels">
    <Tabs full-height>
      <Tab
        v-for="editorSidePanelType in editorSidePanelTypes"
        :key="editorSidePanelType.getType()"
        :title="editorSidePanelType.label"
      >
        <p>Selected: {{ selectedNode?.id }}</p>
        <component
          :is="editorSidePanelType.component"
          :class="`side-panels__panel side-panels__panel-${editorSidePanelType.type}`"
        />
      </Tab>
    </Tabs>
  </aside>
</template>

<script setup>
import { inject, useStore, useContext, computed } from '@nuxtjs/composition-api'

const store = useStore()
const { app } = useContext()

const currentWorkflow = inject('currentWorkflow')
const selectedNode = computed(() =>
  store.getters['automationWorkflowNode/getSelected'](currentWorkflow.value)
)

const sidePanelContext = computed(() => {
  if (!selectedNode) {
    return { workflow: currentWorkflow }
  }
  return {
    node: selectedNode,
    workflow: currentWorkflow,
  }
})

const editorSidePanelTypes = computed(() =>
  app.$registry.getOrderedList('editorSidePanel')
)

console.log(sidePanelContext)
</script>
