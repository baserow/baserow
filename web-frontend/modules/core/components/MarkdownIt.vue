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
})

// Keep a single markdown-it instance per component instance.
const Markdown = MarkdownIt?.default || MarkdownIt
const md = new Markdown()
const baseRules = { ...md.renderer.rules }

// The hash makes sure the data is updated if the content changes.
const contentHash = computed(() => generateHash(props.content))

// Use ref + watcher to avoid side effects in computed
const htmlContent = ref('')

const renderMarkdown = () => {
  md.renderer.rules = { ...baseRules, ...props.rules }
  htmlContent.value = md.render(props.content)
}

watch(() => [props.content, props.rules], renderMarkdown, {
  deep: true,
  immediate: true,
})
</script>
