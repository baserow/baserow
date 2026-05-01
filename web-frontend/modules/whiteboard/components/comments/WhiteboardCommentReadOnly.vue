<template>
  <RichTextEditor
    :model-value="message || emptyMessage"
    :mentionable-users="[]"
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
  },
  data() {
    return { emptyMessage: EMPTY }
  },
}
</script>
