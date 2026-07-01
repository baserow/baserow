<template>
  <ul class="context__menu">
    <li
      v-for="nodeType in nodeTypes"
      :key="nodeType.getType()"
      class="context__menu-item"
    >
      <a
        v-tooltip="
          nodeType.isDeactivatedReason({ workspace: resolvedWorkspace })
        "
        class="context__menu-item-link context__menu-item-link--with-desc"
        :class="{
          disabled: nodeType.isDeactivated({ workspace: resolvedWorkspace }),
        }"
        @click="onChange(nodeType)"
      >
        <span class="context__menu-item-title" :title="nodeType.name">
          <i
            v-if="!nodeType.image"
            class="context__menu-item-icon"
            :class="nodeType.iconClass"
          />
          <img
            v-else
            :alt="nodeType.name"
            :src="nodeType.image"
            class="context__menu-item-icon"
          />
          <span class="context__menu-item-title-text">
            {{ nodeType.name }}
          </span>
          <component
            :is="component"
            v-for="(component, index) in getNodeContextComponents(nodeType)"
            :key="index"
            :workflow="resolvedWorkflow"
            :automation="resolvedAutomation"
            :node="getNodeContextNode(nodeType)"
            :node-type="nodeType"
          />
        </span>
        <div class="context__menu-item-description">
          {{ nodeType.description }}
        </div>
        <component
          :is="getDeactivatedClickModal(nodeType)[0]"
          v-if="getDeactivatedClickModal(nodeType) !== null"
          :ref="`deactivatedClickModal_${nodeType.getType()}`"
          v-bind="getDeactivatedClickModal(nodeType)[1]"
          :name="nodeType.name"
          :workspace="resolvedWorkspace"
        ></component>
      </a>
    </li>
  </ul>
</template>

<script>
import { unref } from 'vue'
import context from '@baserow/modules/core/mixins/context'
export default {
  name: 'WorkflowNodeContext',
  mixins: [context],
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
  emits: ['change'],
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
    /**
     * Returns an array of node types that can be listed in the context.
     * If we are offering the option to replace an existing node's type,
     * then we will omit `this.node.type` from the array, and then present
     * other nodes of the same 'category' (i.e. trigger or action). If we
     * aren't replacing an existing node, then we will show all node types
     * for a single category (i.e. trigger or action), depending on whether
     * there is a trigger or not.
     */
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
  },
  methods: {
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
