<template>
  <!-- eslint-disable-next-line vue/no-v-html vue/no-v-text-v-html-on-component -->
  <component
    :is="tag"
    :key="contentHash"
    class="markdown"
    v-html="htmlContent"
    @click="$emit('click', $event)"
  />
</template>

<script setup>
import { generateHash } from '@baserow/modules/core/utils/hashing'
const emit = defineEmits(['click'])

const props = defineProps({
  content: {
    required: true,
    type: String,
  },
  tag: {
    required: false,
    type: String,
    default: 'div',
  },
  rules: {
    required: false,
    type: Object,
    default: () => ({}),
  },
})

// Keep a single markdown-it instance per component instance.
let md
let baseRules

const initMarkdown = async () => {
  if (md) return md

  const Markdown = (await import('markdown-it')).default
  md = new Markdown()
  baseRules = { ...md.renderer.rules }

  return md
}

// The hash makes sure the data are updated if the content changes.
const contentHash = computed(() => generateHash(props.content))

const markdownAsync = await useAsyncData(
  () => `markdown-it:${contentHash.value}`,
  async () => {
    const instance = await initMarkdown()

    // Always start from the base renderer rules then apply overrides.
    instance.renderer.rules = { ...baseRules, ...props.rules }

    return instance.render(props.content)
  },
  {
    watch: [() => props.content, () => props.rules],
    default: () => '',
  }
)

const htmlContent = computed(() => markdownAsync.data.value || '')
</script>
