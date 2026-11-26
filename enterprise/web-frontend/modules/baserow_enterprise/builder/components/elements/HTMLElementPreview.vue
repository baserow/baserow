<template>
  <iframe
    ref="frame"
    class="html-element__preview"
    :class="{ 'html-element__preview--interactive': interactive }"
    :title="$t('htmlElement.previewTitle')"
    :srcdoc="html"
    sandbox="allow-same-origin"
    :tabindex="interactive ? null : -1"
    :height="height"
    @load="onLoad"
  />
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  html: { type: String, required: true },
  interactive: { type: Boolean, default: false },
})

const frame = ref(null)
const height = ref(150)
let observer

function disconnect() {
  observer?.disconnect()
}

function onLoad() {
  disconnect()
  const document = frame.value.contentDocument
  // A snippet can navigate its frame to a cross-origin document.
  if (!document?.body) return

  // Same-origin access lets the editor measure the document. Scripts stay
  // disabled, including in nested frames, because allow-scripts is absent.
  const inherited = getComputedStyle(frame.value)
  const defaults = document.createElement('style')
  defaults.textContent = `
    html, body { margin: 0; }
    body {
      display: flow-root;
      font-family: ${inherited.fontFamily};
      font-size: ${inherited.fontSize};
      line-height: ${inherited.lineHeight};
      color: ${inherited.color};
    }
  `
  document.head.prepend(defaults)
  for (const property of inherited) {
    if (property.startsWith('--')) {
      document.documentElement.style.setProperty(
        property,
        inherited.getPropertyValue(property)
      )
    }
  }

  const resize = () => {
    const contentHeight = Math.max(
      document.body.scrollHeight,
      document.body.getBoundingClientRect().height
    )
    // A finite cap prevents viewport-relative content from resizing its own
    // viewport indefinitely. Taller content remains scrollable inside the frame.
    height.value = Math.min(600, Math.max(48, Math.ceil(contentHeight)))
  }
  observer = new ResizeObserver(resize)
  observer.observe(document.body)
  resize()
}

watch(() => props.html, disconnect)
onBeforeUnmount(disconnect)
</script>
