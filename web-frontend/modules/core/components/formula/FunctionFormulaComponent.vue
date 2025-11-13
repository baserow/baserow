<template>
  <NodeViewWrapper as="span" class="function-formula-component">
    <span class="function-formula-component__name">{{ functionName }}(</span>
  </NodeViewWrapper>
</template>

<script>
import { NodeViewWrapper } from '@tiptap/vue-2'
import formulaComponent from '@baserow/modules/core/mixins/formulaComponent'

export default {
  name: 'FunctionFormulaComponent',
  components: {
    NodeViewWrapper,
  },
  mixins: [formulaComponent],
  computed: {
    functionName() {
      return this.node?.attrs?.functionName || ''
    },
  },
}
</script>
