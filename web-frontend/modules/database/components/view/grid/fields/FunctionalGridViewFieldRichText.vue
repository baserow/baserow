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
import { replaceImagesWithPlaceholder } from '@baserow/modules/core/editor/richTextImageUtils'

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
      const { value, workspaceId } = this

      let preview = replaceImagesWithPlaceholder(value)
      if (preview.length > maxLen) {
        preview = preview.substring(0, maxLen) + '...'
      }

      const workspace = this.$store.getters['workspace/get'](workspaceId)
      const loggedUserId = this.$store.getters['auth/getUserId']

      return parseMarkdown(preview, {
        openLinkOnClick: false,
        enableImages: false,
        workspaceUsers: workspace ? workspace.users : null,
        loggedUserId,
      })
    },
  },
}
</script>
