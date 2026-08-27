<!-- eslint-disable vue/no-v-html vue/no-v-text-v-html-on-component -->
<template>
  <span
    v-if="inline"
    :key="contentHash"
    class="markdown markdown--inline"
    @click="$emit('click', $event)"
    v-html="htmlContent"
  />
  <div
    v-else
    :key="contentHash"
    class="markdown"
    @click="$emit('click', $event)"
    v-html="htmlContent"
  />
</template>

<script setup>
import { computed, ref, watch } from 'vue'
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
   * Render the content with `renderInline` inside a `<span>` instead of parsing
   * block syntax into a `<div>`. Block syntax (headings, lists, tables...) then
   * stays literal text, which is what single-line surfaces like labels, tags or
   * dropdown options want.
   */
  inline: {
    required: false,
    type: Boolean,
    default: false,
  },
  /**
   * Names of the markdown-it rules to disable, e.g. `['link', 'image']`. The
   * policy is owned by the caller because it differs per surface.
   */
  disabledRules: {
    required: false,
    type: Array,
    default: () => [],
  },
})

// Keep a single markdown-it instance per component instance, so disabling rules
// can't leak to other consumers.
const Markdown = MarkdownIt?.default || MarkdownIt
const md = new Markdown()
const baseRules = { ...md.renderer.rules }
let appliedDisabledRules = []

// The hash makes sure the data is updated if the content changes.
const contentHash = computed(() => generateHash(props.content))

// Use ref + watcher to avoid side effects in computed
const htmlContent = ref('')

const renderMarkdown = () => {
  // Re-enable what was disabled by a previous render before applying the
  // current list, otherwise a changed `disabledRules` would accumulate.
  md.enable(appliedDisabledRules, true)
  md.disable(props.disabledRules, true)
  appliedDisabledRules = [...props.disabledRules]

  md.renderer.rules = { ...baseRules, ...props.rules }
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
