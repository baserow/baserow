<!-- eslint-disable vue/no-v-html vue/no-v-text-v-html-on-component -->
<template>
  <component
    :is="inline ? 'span' : 'div'"
    :key="contentHash"
    class="markdown"
    :class="{ 'markdown--inline': inline }"
    @click="$emit('click', $event)"
    v-html="htmlContent"
  />
</template>

<script setup>
import { ref, watch } from 'vue'
import { generateHash } from '@baserow/modules/core/utils/hashing'
import { renderMarkdown } from '@baserow/modules/core/utils/markdown'

defineEmits(['click'])

const props = defineProps({
  content: {
    required: true,
    type: String,
  },
  rules: {
    required: false,
    type: Object,
    default: () => ({}),
  },
  openLinksInNewTab: {
    required: false,
    type: Boolean,
    default: false,
  },
  /**
   * Renders the content as inline markdown: only the inline syntax (emphasis,
   * links, code, ...) applies, and the result has no wrapping paragraph, so
   * it inherits the typography of wherever it is placed.
   */
  inline: {
    required: false,
    type: Boolean,
    default: false,
  },
  /**
   * The names of the markdown-it rules to switch off for this component, e.g.
   * `['image', 'link']`. Unknown names are ignored.
   */
  disabledRules: {
    required: false,
    type: Array,
    default: () => [],
  },
})

// The hash makes sure the data is updated if the content changes.
const contentHash = computed(() => generateHash(props.content))

// Use ref + watcher to avoid side effects in computed
const htmlContent = ref('')

const linkInNewTabRules = {
  link_open: (tokens, idx, options, env, self) => {
    if (tokens[idx].attrIndex('target') < 0) {
      tokens[idx].attrPush(['target', '_blank'])
    }
    if (tokens[idx].attrIndex('rel') < 0) {
      tokens[idx].attrPush(['rel', 'noopener noreferrer'])
    }
    return self.renderToken(tokens, idx, options)
  },
}

watch(
  () => [
    props.content,
    props.rules,
    props.openLinksInNewTab,
    props.inline,
    props.disabledRules,
  ],
  () => {
    htmlContent.value = renderMarkdown(props.content, {
      rules: {
        ...(props.openLinksInNewTab ? linkInNewTabRules : {}),
        ...props.rules,
      },
      inline: props.inline,
      disabledRules: props.disabledRules,
    })
  },
  {
    deep: true,
    immediate: true,
  }
)
</script>
