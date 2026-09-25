<!-- eslint-disable vue/no-v-html -->
<template>
  <div
    class="field-rich-text--preview grid-view__cell grid-field-rich-text__cell"
  >
    <div
      class="grid-field-rich-text__cell-content grid-field-rich-text__cell-content--preview"
      v-html="renderFormattedValue()"
    ></div>
  </div>
</template>

<script>
import { parseMarkdown } from '@baserow/modules/core/editor/markdown'
import { trimUnfinishedImageRef } from '@baserow/modules/core/editor/richTextImageUtils'

export default {
  name: 'FunctionalGridViewFieldRichText',
  props: {
    value: {
      type: String,
      default: '',
    },
    workspaceId: {
      type: Number,
      required: true,
    },
  },
  methods: {
    renderFormattedValue() {
      const maxLen = 200
      // Bound the regex work: large cells re-render on every scroll. The cut can
      // land inside an image ref, so drop a trailing unfinished one.
      const sliceMargin = 500
      const { value, workspaceId } = this

      const preview = trimUnfinishedImageRef(
        (value || '').slice(0, sliceMargin)
      )
      const workspace = this.$store.getters['workspace/get'](workspaceId)
      const loggedUserId = this.$store.getters['auth/getUserId']

      let html = parseMarkdown(preview, {
        openLinkOnClick: false,
        enableImages: false,
        workspaceUsers: workspace ? workspace.users : null,
        loggedUserId,
      })

      if (value && value.length > maxLen) {
        html += '...'
      }
      return html
    },
  },
}
</script>
