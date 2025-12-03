import { nodeViewProps } from '@tiptap/vue-3'

export default {
  props: nodeViewProps,
  methods: {
    emitToEditor(...args) {
      this.$parent.$emit(...args)
    },
  },
}
