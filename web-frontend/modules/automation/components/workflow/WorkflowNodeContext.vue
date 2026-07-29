<template>
  <Context
    ref="context"
    class="workflow-node__context"
    max-height-if-outside-viewport
    @shown="focusMenu"
  >
    <WorkflowAddNodeMenu
      ref="menu"
      :node="node"
      :only-trigger="onlyTrigger"
      @change="onChange($event)"
      @close="hide"
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
  emits: ['change'],
  methods: {
    async focusMenu() {
      await this.$nextTick()
      await this.$refs.menu?.focus()
    },
    onChange(nodeType) {
      this.hide()
      this.$emit('change', nodeType)
    },
  },
}
</script>
