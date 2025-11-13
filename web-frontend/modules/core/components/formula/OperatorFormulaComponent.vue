<template>
  <NodeViewWrapper
    as="span"
    class="operator-formula-component"
    :contenteditable="false"
  >
    <span class="operator-formula-component__symbol">{{ operatorSymbol }}</span>
  </NodeViewWrapper>
</template>

<script>
import { NodeViewWrapper } from '@tiptap/vue-2'
import formulaComponent from '@baserow/modules/core/mixins/formulaComponent'

export default {
  name: 'OperatorFormulaComponent',
  components: {
    NodeViewWrapper,
  },
  mixins: [formulaComponent],
  computed: {
    operatorSymbol() {
      return this.node?.attrs?.operatorSymbol || ''
    },
  },
}
</script>
