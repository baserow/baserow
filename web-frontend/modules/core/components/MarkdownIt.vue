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
import MarkdownIt from 'markdown-it'

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
   * The names of the markdown-it rules to switch off for this instance, e.g.
   * `['image', 'link']`. Unknown names are ignored.
   */
  disabledRules: {
    required: false,
    type: Array,
    default: () => [],
  },
})

// Keep a single markdown-it instance per component instance.
const Markdown = MarkdownIt?.default || MarkdownIt
const md = new Markdown()
const baseRules = { ...md.renderer.rules }
// The rules switched off on this instance, so that a change of
// `disabledRules` first switches the previous ones back on.
let currentlyDisabled = []

// The hash makes sure the data is updated if the content changes.
const contentHash = computed(() => generateHash(props.content))

// Use ref + watcher to avoid side effects in computed
const htmlContent = ref('')

const renderMarkdown = () => {
  md.renderer.rules = { ...baseRules, ...props.rules }
  if (currentlyDisabled.length > 0) {
    md.enable(currentlyDisabled, true)
  }
  currentlyDisabled = [...props.disabledRules]
  if (currentlyDisabled.length > 0) {
    md.disable(currentlyDisabled, true)
  }
  htmlContent.value = props.inline
    ? md.renderInline(props.content)
    : md.render(props.content)
}

watch(
  () => [props.content, props.rules, props.inline, props.disabledRules],
  renderMarkdown,
  {
    deep: true,
    immediate: true,
  }
)
</script>
