<template>
  <RichTextEditor
    :model-value="message || emptyMessage"
    :mentionable-users="mentionableUsers"
    :editable="false"
    :enable-rich-text-formatting="false"
  />
</template>

<script>
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor'

const EMPTY = { type: 'doc', content: [{ type: 'paragraph' }] }

export default {
  name: 'WhiteboardCommentReadOnly',
  components: { RichTextEditor },
  props: {
    message: { type: [Object, String], default: null },
    // The whiteboard's own workspace, threaded down as a prop from the
    // page so the mention extension resolves users against the
    // board's workspace rather than `workspace/getSelected` (which can
    // flip while the user navigates between workspaces and produced
    // the "user gone" strike-through bug).
    workspace: { type: Object, required: true },
  },
  data() {
    return { emptyMessage: EMPTY }
  },
  computed: {
    mentionableUsers() {
      return this.workspace?.users || []
    },
  },
}
</script>
