<template>
  <Context class="workflow-node__context">
    <WorkflowAddNodeMenu
      :node="node"
      :only-trigger="onlyTrigger"
      @change="onChange($event)"
    ></WorkflowAddNodeMenu>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import WorkflowAddNodeMenu from './WorkflowAddNodeMenu.vue'
export default {
  name: 'WorkflowNodeContext',
  components: { WorkflowAddNodeMenu },
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
  methods: {
    onChange(nodeType) {
      this.hide()
      this.$emit('change', nodeType)
    },
  },
}
</script>
