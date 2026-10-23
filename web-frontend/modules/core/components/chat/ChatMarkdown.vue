<template>
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div class="chat-markdown" @click="followLink" v-html="html"></div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import MarkdownIt from 'markdown-it'

// A rendered image would load any URL, which can carry conversation data away.
const markdown = new MarkdownIt({ html: false, linkify: true }).disable('image')

const props = defineProps({
  /** The markdown to render. */
  content: { type: String, default: '' },
})

const router = useRouter()
const html = computed(() => markdown.render(props.content))

/**
 * Opens pages of this app in the router and every other link in a new tab,
 * leaving clicks with a modifier key to the browser.
 *
 * @param {MouseEvent} event The click on the rendered content.
 */
function followLink(event) {
  const link = event.target.closest('a')
  const modified =
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  if (!link || modified) return
  event.preventDefault()
  const url = new URL(link.href)
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
