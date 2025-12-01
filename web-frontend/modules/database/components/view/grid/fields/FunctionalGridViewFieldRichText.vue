<!-- eslint-disable vue/no-v-html -->
<template functional>
  <div
    class="field-rich-text--preview grid-view__cell grid-field-rich-text__cell"
  >
    <div
      class="grid-field-rich-text__cell-content grid-field-rich-text__cell-content--preview"
      v-html="$options.methods.renderFormattedValue(parent, props)"
    ></div>
  </div>
</template>

<script>
import { parseMarkdown } from '@baserow/modules/core/editor/markdown'

export default {
  name: 'FunctionalGridViewFieldRichText',
  methods: {
    renderFormattedValue(parent, props) {
      const maxLen = 200
      const { value, workspaceId } = props

      // Take only a part of the text as a preview to avoid rendering a huge amount of
      // HTML that could slow down the page and won't be visible anyway
      let preview = value || ''
      if (preview.length > maxLen) {
        preview = value.substring(0, maxLen) + '...'
      }

      const workspace = parent.$store.getters['workspace/get'](workspaceId)
      const loggedUserId = parent.$store.getters['auth/getUserId']

      return parseMarkdown(preview, {
        openLinkOnClick: false,
        workspaceUsers: workspace ? workspace.users : null,
        loggedUserId,
      })
    },
  },
}
</script>
