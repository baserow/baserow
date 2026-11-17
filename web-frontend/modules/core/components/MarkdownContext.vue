<template>
  <Context ref="context" overflow-scroll max-height-if-outside-viewport>
    <div class="markdown-context">
      <div class="markdown-context__title">{{ title }}</div>
      <MarkdownIt
        class="markdown-context__content"
        :content="content"
        :rules="RULES"
        open-links-in-new-tab
      />
    </div>
  </Context>
</template>

<script setup>
import { ref } from 'vue'
import { escapeHtml } from '@baserow/modules/core/utils/string'

/**
 * A popover that shows a Markdown text written by a user, such as a description
 * or a note.
 */
defineProps({
  title: {
    type: String,
    required: true,
  },
  content: {
    type: String,
    required: true,
  },
})

// Raw HTML is never rendered by the shared parser. An image is replaced by its
// alternative text, so reading a note never loads a remote resource.
const RULES = {
  image: (tokens, idx) => escapeHtml(tokens[idx].content),
}

const context = ref(null)

const toggle = (...args) => context.value?.toggle(...args)
const hide = (...args) => context.value?.hide(...args)

defineExpose({ toggle, hide })
</script>
