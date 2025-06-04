<template>
  <Context class="workflow_node_context">
    <Dropdown
      size="large"
      show-search
      open-on-mount
      :show-input="false"
      :search-text="$t('createWorkflowNodeContext.searchPlaceholder')"
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
    </Dropdown>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
export default {
  name: 'CreateWorkflowNodeContext',
  mixins: [context],
  props: {
    lastNodeId: {
      type: [Number, String],
      required: false,
      default: null,
    },
    workflowHasTrigger: {
      type: Boolean,
      required: true,
    },
  },
  computed: {
    nodeTypes() {
      return Object.values(this.$registry.getAll('node')).filter((nodeType) => {
        return this.workflowHasTrigger
          ? nodeType.isWorkflowAction
          : nodeType.isTrigger
      })
    },
  },
  methods: {
    onChange(nodeType) {
      this.hide()
      this.$emit('change', nodeType, this.lastNodeId)
    },
  },
}
</script>
