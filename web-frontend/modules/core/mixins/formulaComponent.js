import { nodeViewProps } from '@tiptap/vue-3'

export default {
  props: nodeViewProps,
  methods: {
    emitToEditor(eventName, ...args) {
      this.editor.emit(eventName, ...args)
    },
  },
}
