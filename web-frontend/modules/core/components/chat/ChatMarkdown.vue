<template>
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div class="chat-markdown" @click="followLink" v-html="html"></div>
</template>

<script>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import MarkdownIt from 'markdown-it'

// A rendered image would load any URL, which can carry conversation data away.
const markdown = new MarkdownIt({ html: false, linkify: true }).disable('image')
</script>

<script setup>
const props = defineProps({ content: { type: String, default: '' } })

const router = useRouter()
const html = computed(() => markdown.render(props.content))

/** App links open in the router, other web links in a new tab. */
function followLink(event) {
  const link = event.target.closest('a')
  const modified =
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  if (!link || modified) return
  const url = new URL(link.href)
  if (!['http:', 'https:'].includes(url.protocol)) return
  event.preventDefault()
  const path = url.pathname + url.search + url.hash
  if (
    url.origin === window.location.origin &&
    router.resolve(path).matched.length
  ) {
    router.push(path)
  } else {
    window.open(url.href, '_blank', 'noopener,noreferrer')
  }
}
</script>
