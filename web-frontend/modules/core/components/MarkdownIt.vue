<!-- eslint-disable vue/no-v-html vue/no-v-text-v-html-on-component -->
<template>
  <div
    :key="contentHash"
    class="markdown"
    @click="$emit('click', $event)"
    v-html="htmlContent"
  />
</template>

<script setup>
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
})

// Keep a single markdown-it instance per component instance.
const Markdown = MarkdownIt?.default || MarkdownIt
const md = new Markdown()
const baseRules = { ...md.renderer.rules }

// The hash makes sure the data are updated if the content changes.
const contentHash = computed(() => generateHash(props.content))

const htmlContent = computed(() => {
  // Always start from the base renderer rules then apply overrides.
  md.renderer.rules = { ...baseRules, ...props.rules }
  return md.render(props.content)
})
</script>
