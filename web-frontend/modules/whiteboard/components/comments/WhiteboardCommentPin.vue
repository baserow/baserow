<template>
  <button
    class="whiteboard-comment-pin"
    :class="{
      'whiteboard-comment-pin--resolved': thread.resolved,
      'whiteboard-comment-pin--open': open,
      'whiteboard-comment-pin--draft': draft,
    }"
    :style="positionStyle"
    type="button"
    @click.stop="$emit('open')"
  >
    <span class="whiteboard-comment-pin__label">{{ pinLabel }}</span>
    <span v-if="replyCount > 0" class="whiteboard-comment-pin__count">
      {{ replyCount }}
    </span>
  </button>
</template>

<script>
export default {
  name: 'WhiteboardCommentPin',
  props: {
    thread: { type: Object, required: true },
    viewport: { type: Object, required: true },
    open: { type: Boolean, default: false },
    draft: { type: Boolean, default: false },
  },
  emits: ['open'],
  computed: {
    positionStyle() {
      // `viewport` can briefly be `null` between the moment the layer
      // first renders and the moment Excalidraw assigns its imperative
      // API (we have a controller object but `apiRef.current` is still
      // null). Hide the pin until coordinates are available.
      if (!this.viewport) return { display: 'none' }
      return {
        transform: `translate(${this.viewport.x}px, ${this.viewport.y}px)`,
      }
    },
    replyCount() {
      // 1 (top-level) + replies.length, displayed as just the reply count
      // following Figma's convention.
      if (!this.thread.replies) return 0
      return this.thread.replies.length
    },
    pinLabel() {
      // Drafts have no author yet — show a generic "+" so the user
      // knows where their pending pin will land.
      if (this.draft) return '+'
      const name = (this.thread.first_name || '').trim()
      if (!name) return '?'
      // Take the first letter of up to two whitespace-separated parts —
      // "Bram Wiepjes" -> "BW", "Bram" -> "B". Baserow stores the full
      // display name in `first_name`.
      const parts = name.split(/\s+/).filter(Boolean).slice(0, 2)
      return parts.map((p) => p[0].toUpperCase()).join('')
    },
  },
}
</script>

<style lang="scss" scoped>
.whiteboard-comment-pin {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: auto;
  width: 32px;
  height: 32px;
  border-radius: 50% 50% 50% 4px;
  background: #ffd866;
  color: #1e1e1e;
  border: 2px solid #fff;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  // Anchor the pin's bottom-left tip on the scene point, like Figma.
  transform-origin: 0 100%;
  margin-left: -2px;
  margin-top: -32px;
  &:hover {
    background: #ffce4d;
  }
  &--open {
    outline: 2px solid #1e1e1e;
  }
  &--resolved {
    background: #d0d4d8;
    color: #4a4a4a;
  }
  &--draft {
    background: #5b8ff9;
    color: #fff;
  }
}
.whiteboard-comment-pin__label {
  pointer-events: none;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  line-height: 1;
}
.whiteboard-comment-pin__count {
  position: absolute;
  top: -6px;
  right: -6px;
  background: #1e1e1e;
  color: #fff;
  font-size: 10px;
  border-radius: 9px;
  padding: 0 5px;
  min-width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
</style>
