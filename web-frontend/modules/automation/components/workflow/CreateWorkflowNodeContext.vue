<template>
  <Context class="workflow-node__context" @shown="$refs.nodeDropdown.show()">
    <Dropdown
      ref="nodeDropdown"
      size="large"
      show-search
      open-on-mount
      :show-input="false"
      :search-text="
        !lastNodeId
          ? $t('createWorkflowNodeContext.searchPlaceholderTrigger')
          : $t('createWorkflowNodeContext.searchPlaceholderActions')
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
        {{ $t('createWorkflowNodeContext.noResults') }}
      </template>
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
  },
  computed: {
    nodeTypes() {
      return Object.values(this.$registry.getAll('node')).filter((nodeType) => {
        return !this.lastNodeId ? nodeType.isTrigger : nodeType.isWorkflowAction
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
