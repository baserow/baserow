<template>
  <div class="workflow-add-node-menu">
    <MenuList
      :items="menuItems"
      :searchable="!editingTriggerNode"
      :search-placeholder="$t('workflowNodeContext.searchPlaceholderActions')"
      :empty-text="$t('workflowNodeContext.noResults')"
      @select="onMenuItemSelected"
      @disabled-click="onMenuItemSelected"
      @close="$emit('close')"
    >
      <template #item-meta="{ item }">
        <template v-if="item.meta">
          <component
            :is="component"
            v-for="(component, index) in getNodeContextComponents(item.meta)"
            :key="index"
            :workflow="resolvedWorkflow"
            :automation="resolvedAutomation"
            :node="getNodeContextNode(item.meta)"
            :node-type="item.meta"
          />
        </template>
      </template>
    </MenuList>
    <template v-for="nodeType in nodeTypes" :key="nodeType.getType()">
      <component
        :is="getDeactivatedClickModal(nodeType)[0]"
        v-if="getDeactivatedClickModal(nodeType) !== null"
        :ref="`deactivatedClickModal_${nodeType.getType()}`"
        v-bind="getDeactivatedClickModal(nodeType)[1]"
        :name="nodeType.name"
        :workspace="resolvedWorkspace"
      />
    </template>
  </div>
</template>

<script>
import { unref } from 'vue'
import MenuList from '@baserow/modules/core/components/MenuList'

export default {
  name: 'WorkflowAddNodeMenu',
  components: { MenuList },
  inject: ['workspace', 'workflow', 'automation'],
  props: {
    node: {
      type: Object,
      required: false,
      default: () => null,
    },
    onlyTrigger: {
      type: Boolean,
      required: false,
      default: () => false,
    },
  },
  emits: ['change', 'close'],
  computed: {
    resolvedAutomation() {
      return unref(this.automation)
    },
    resolvedWorkflow() {
      return unref(this.workflow)
    },
    resolvedWorkspace() {
      return unref(this.workspace)
    },
    editingTriggerNode() {
      return this.onlyTrigger
    },
    nodeTypes() {
      return this.$registry
        .getOrderedList('node')
        .filter(
          (nodeType) =>
            this.node?.type !== nodeType.type &&
            (this.editingTriggerNode
              ? nodeType.isTrigger
              : nodeType.isWorkflowAction)
        )
    },
    menuItems() {
      return this.nodeTypes.map((nodeType) =>
        this.makeNodeTypeMenuItem(nodeType)
      )
    },
  },
  methods: {
    makeNodeTypeMenuItem(nodeType) {
      return {
        id: `node-${nodeType.getType()}`,
        label: nodeType.name,
        value: nodeType.getType(),
        icon: nodeType.iconClass,
        image: nodeType.image,
        description: nodeType.description,
        disabled: nodeType.isDeactivated({
          workspace: this.resolvedWorkspace,
        }),
        disabledReason: nodeType.isDeactivatedReason({
          workspace: this.resolvedWorkspace,
        }),
        meta: nodeType,
      }
    },
    onMenuItemSelected(item) {
      this.onChange(item.meta)
    },
    onChange(nodeType) {
      if (nodeType.isDeactivated({ workspace: this.resolvedWorkspace })) {
        const deactivatedClickModal = this.getDeactivatedClickModal(nodeType)
        if (deactivatedClickModal !== null) {
          this.$refs[`deactivatedClickModal_${nodeType.getType()}`][0].show()
        }
        return
      }
      this.$emit('change', nodeType.getType())
    },
    getDeactivatedClickModal(nodeType) {
      return nodeType.getDeactivatedClickModal({
        workspace: this.resolvedWorkspace,
      })
    },
    getNodeContextNode(nodeType) {
      return {
        ...(this.node || {}),
        type: nodeType.getType(),
      }
    },
    getNodeContextComponents(nodeType) {
      const node = this.getNodeContextNode(nodeType)
      return Object.values(this.$registry.getAll('plugin')).reduce(
        (components, plugin) =>
          components.concat(
            plugin.getAutomationWorkflowNodeContextComponents({
              workflow: this.resolvedWorkflow,
              automation: this.resolvedAutomation,
              node,
              nodeType,
            })
          ),
        []
      )
    },
  },
}
</script>
