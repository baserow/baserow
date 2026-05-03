<template>
  <div
    ref="popup"
    class="whiteboard-comment-thread"
    :style="positionStyle"
    @click.stop
  >
    <div class="whiteboard-comment-thread__header">
      <span class="whiteboard-comment-thread__title">
        {{
          isDraft
            ? $t('whiteboardComments.newComment')
            : $t('whiteboardComments.thread')
        }}
      </span>
      <button
        v-if="!isDraft && !readOnly && !thread.resolved"
        class="whiteboard-comment-thread__resolve"
        type="button"
        :disabled="resolving"
        @click="onResolve(true)"
      >
        {{
          resolving
            ? $t('whiteboardComments.resolving')
            : $t('whiteboardComments.resolve')
        }}
      </button>
      <button
        v-else-if="!isDraft && !readOnly && thread.resolved"
        class="whiteboard-comment-thread__resolve"
        type="button"
        :disabled="resolving"
        @click="onResolve(false)"
      >
        {{ $t('whiteboardComments.reopen') }}
      </button>
      <button
        class="whiteboard-comment-thread__close"
        type="button"
        @click="$emit('close')"
      >
        ×
      </button>
    </div>
    <div v-if="!isDraft" class="whiteboard-comment-thread__items">
      <WhiteboardCommentItem
        v-for="comment in items"
        :key="comment.id"
        :comment="comment"
        :workspace="workspace"
        :read-only="readOnly"
      />
    </div>
    <div v-if="!readOnly" class="whiteboard-comment-thread__editor">
      <WhiteboardCommentEditor
        ref="editor"
        :loading="postingNew"
        :placeholder="
          isDraft
            ? $t('whiteboardComments.placeholderNew')
            : $t('whiteboardComments.placeholderReply')
        "
        :workspace="workspace"
        :autofocus="isDraft"
        @posted="onPosted"
        @cancelled="onCancelled"
      />
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'
import WhiteboardCommentItem from '@baserow/modules/whiteboard/components/comments/WhiteboardCommentItem.vue'
import WhiteboardCommentEditor from '@baserow/modules/whiteboard/components/comments/WhiteboardCommentEditor.vue'

export default {
  name: 'WhiteboardCommentThread',
  components: { WhiteboardCommentItem, WhiteboardCommentEditor },
  props: {
    whiteboard: { type: Object, required: true },
    workspace: { type: Object, required: true },
    thread: { type: Object, default: null },
    draftPin: { type: Object, default: null },
    viewport: { type: Object, required: true },
    wrapperWidth: { type: Number, default: 0 },
    wrapperHeight: { type: Number, default: 0 },
    readOnly: { type: Boolean, default: false },
  },
  emits: ['close', 'cancel-draft'],
  data() {
    return {
      popupWidth: 320,
      popupHeight: 320,
    }
  },
  computed: {
    ...mapGetters({
      postingDraft: 'whiteboardComments/isPostingDraft',
      postingReplyForThreadId: 'whiteboardComments/getPostingReplyForThreadId',
    }),
    isDraft() {
      return !this.thread && !!this.draftPin
    },
    postingNew() {
      if (this.isDraft) return this.postingDraft
      return this.postingReplyForThreadId === this.thread?.id
    },
    resolving() {
      if (!this.thread) return false
      return (
        this.$store.getters['whiteboardComments/getCommentLoadingState'](
          this.thread.id
        ) === 'resolving'
      )
    },
    items() {
      if (!this.thread) return []
      return [this.thread, ...(this.thread.replies || [])]
    },
    positionStyle() {
      // Default: anchor to the right of the pin tip. If that would push
      // the popup past the right edge of the wrapper, flip to the left
      // side of the pin instead. Same idea for the bottom edge —
      // shift up so the popup stays inside the canvas. Falls back to a
      // small margin from the edge when the popup is taller/wider than
      // the wrapper itself.
      const margin = 8
      const offsetX = 14 // gap between pin tip and popup
      const wrapperW = this.wrapperWidth || 0
      const wrapperH = this.wrapperHeight || 0
      const popupW = this.popupWidth || 320
      const popupH = this.popupHeight || 320
      const pinX = this.viewport.x
      const pinY = this.viewport.y

      let x = pinX + offsetX
      // Flip to the left if there's no room on the right.
      if (wrapperW > 0 && x + popupW + margin > wrapperW) {
        x = pinX - offsetX - popupW
      }
      // Clamp inside the wrapper.
      if (x + popupW + margin > wrapperW) x = wrapperW - popupW - margin
      if (x < margin) x = margin

      let y = pinY - offsetX
      if (wrapperH > 0 && y + popupH + margin > wrapperH) {
        y = wrapperH - popupH - margin
      }
      if (y < margin) y = margin

      return {
        transform: `translate(${x}px, ${y}px)`,
      }
    },
  },
  mounted() {
    // Defer to the next tick: the popup is mounted from inside a
    // <client-only> + Vuex-driven v-if, and the template ref isn't
    // always populated synchronously when `mounted` fires. Without this
    // guard, `ResizeObserver.observe()` blows up with
    // "Argument 1 is not an object".
    this.$nextTick(() => {
      const el = this.$refs.popup
      if (!el) return
      this._measure()
      if (typeof ResizeObserver === 'undefined') return
      this._ro = new ResizeObserver(() => this._measure())
      this._ro.observe(el)
    })
  },
  beforeUnmount() {
    if (this._ro) {
      this._ro.disconnect()
      this._ro = null
    }
  },
  methods: {
    _measure() {
      const el = this.$refs.popup
      if (!el) return
      this.popupWidth = el.offsetWidth || this.popupWidth
      this.popupHeight = el.offsetHeight || this.popupHeight
    },
    async onPosted(message) {
      // Capture the editor ref synchronously. The editor's `:loading`
      // prop flips during the dispatch and Vue may transiently
      // invalidate the ref while the post is in flight, so calling
      // `clear()` *after* the await without this would silently no-op.
      const editor = this.$refs.editor
      try {
        if (this.isDraft) {
          await this.$store.dispatch('whiteboardComments/postDraftComment', {
            whiteboardId: this.whiteboard.id,
            message,
          })
        } else {
          await this.$store.dispatch('whiteboardComments/postReply', {
            whiteboardId: this.whiteboard.id,
            parentCommentId: this.thread.id,
            message,
          })
        }
      } catch (error) {
        // Surface the failure to the user but keep their typed text
        // intact so they can retry — `clear()` is gated on success.
        notifyIf(error, 'application')
        return
      }
      await this.$nextTick()
      ;(this.$refs.editor || editor)?.clear?.()
    },
    onCancelled() {
      // Cancel always closes the popup. For a draft pin we also drop
      // the unposted draft entirely; for a reply or an in-flight edit
      // closing is enough — the local editor state goes away with the
      // popup and any pending data is discarded.
      if (this.isDraft) {
        this.$emit('cancel-draft')
      } else {
        this.$emit('close')
      }
    },
    async onResolve(resolved) {
      try {
        await this.$store.dispatch('whiteboardComments/setResolved', {
          commentId: this.thread.id,
          resolved,
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
  },
}
</script>

<style lang="scss" scoped>
.whiteboard-comment-thread {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: auto;
  width: 320px;
  max-height: 70vh;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 60;
}
.whiteboard-comment-thread__header {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid #ececec;
  font-size: 14px;
  font-weight: 600;
}
.whiteboard-comment-thread__title {
  flex: 1;
}
.whiteboard-comment-thread__close {
  background: none;
  border: none;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  color: #888;
  padding: 0 4px;
}
.whiteboard-comment-thread__resolve {
  background: none;
  border: 1px solid #d0d4d8;
  border-radius: 4px;
  padding: 4px 8px;
  margin-right: 8px;
  font-size: 12px;
  cursor: pointer;
  &:disabled {
    opacity: 0.6;
    cursor: progress;
  }
}
.whiteboard-comment-thread__items {
  overflow-y: auto;
  max-height: 50vh;
  padding: 4px 0;
}
.whiteboard-comment-thread__editor {
  border-top: 1px solid #ececec;
  // Match the 12px horizontal padding used by `.whiteboard-comment-item`
  // so the reply / new-comment editor's text aligns with the bodies of
  // the items above. The editor itself no longer applies horizontal
  // padding, so this wrapper carries it.
  padding: 8px 12px;
}
</style>
