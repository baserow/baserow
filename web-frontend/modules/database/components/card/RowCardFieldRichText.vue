<!-- eslint-disable vue/no-v-html -->
<template>
  <div
    class="card-rich-text field-rich-text--preview"
    v-html="formattedValue"
  ></div>
</template>

<script>
import { parseMarkdown } from '@baserow/modules/core/editor/markdown'

export default {
  props: {
    value: {
      type: String,
      default: '',
    },
    workspaceId: {
      type: Number,
      required: true,
    },
    enableMentions: {
      type: Boolean,
      default: true,
    },
    enableImages: {
      type: Boolean,
      default: true,
    },
  },
  height: 32,
  computed: {
    formattedValue() {
      const workspace = this.$store.getters['workspace/get'](this.workspaceId)
      const loggedUserId = this.$store.getters['auth/getUserId']

      return parseMarkdown(this.value, {
        openLinkOnClick: true,
        enableImages: this.enableImages,
        workspaceUsers:
          this.enableMentions && workspace ? workspace.users : null,
        loggedUserId,
      })
    },
  },
}
</script>
