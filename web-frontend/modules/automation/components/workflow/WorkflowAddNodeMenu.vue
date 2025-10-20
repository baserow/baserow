<template>
  <ul class="context__menu">
    <li
      v-for="nodeType in nodeTypes"
      :key="nodeType.getType()"
      class="context__menu-item"
    >
      <a
        class="context__menu-item-link context__menu-item-link--with-desc"
        @click="onChange(nodeType.getType())"
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
          {{ nodeType.name }}
        </span>
        <div class="context__menu-item-description">
          {{ nodeType.description }}
        </div>
      </a>
    </li>
  </ul>
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
    onlyTrigger: {
      type: Boolean,
      required: false,
      default: () => false,
    },
  },
  computed: {
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
      this.$emit('change', nodeType)
    },
  },
}
</script>
