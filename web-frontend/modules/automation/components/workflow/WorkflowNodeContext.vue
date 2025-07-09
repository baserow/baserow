<template>
  <Context class="workflow-node__context" @shown="$refs.nodeDropdown.show()">
    <Dropdown
      ref="nodeDropdown"
      size="large"
      show-search
      open-on-mount
      :show-input="false"
      :search-text="
        editingTriggerNode
          ? $t('workflowNodeContext.searchPlaceholderTrigger')
          : $t('workflowNodeContext.searchPlaceholderActions')
      "
      @change="onChange"
    >
      <DropdownItem
        v-for="nodeType in nodeTypes"
        :key="nodeType.getType()"
        :name="nodeType.name"
        :image="nodeType.image"
        :value="nodeType.getType()"
        :description="nodeType.description"
      ></DropdownItem>
      <template #emptyState>
        {{ $t('workflowNodeContext.noResults') }}
      </template>
    </Dropdown>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
export default {
  name: 'WorkflowNodeContext',
  mixins: [context],
  props: {
    node: {
      type: Object,
      required: false,
      default: () => null,
    },
  },
  computed: {
    editingTriggerNode() {
      return this.node
        ? this.$registry.get('node', this.node.type).isTrigger
        : false
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
      this.hide()
      this.$emit('change', nodeType)
    },
  },
}
</script>
