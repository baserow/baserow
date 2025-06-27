<template>
  <Context class="workflow-node__context" @shown="$refs.nodeDropdown.show()">
    <Dropdown
      ref="nodeDropdown"
      size="large"
      show-search
      open-on-mount
      :show-input="false"
      :search-text="
        !workflowHasTrigger || editingTriggerNode
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
    workflowHasTrigger: {
      type: Boolean,
      required: false,
      default: true,
    },
  },
  computed: {
    editingTriggerNode() {
      return this.node
        ? this.$registry.get('node', this.node.type).isTrigger
        : false
    },
    nodeTypes() {
      return Object.values(this.$registry.getAll('node')).filter((nodeType) => {
        return !this.workflowHasTrigger || this.editingTriggerNode
          ? nodeType.isTrigger
          : nodeType.isWorkflowAction
      })
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
