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
      const sliceMargin = 500
      const { value, workspaceId } = this

      let preview = (value || '').slice(0, sliceMargin)
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
