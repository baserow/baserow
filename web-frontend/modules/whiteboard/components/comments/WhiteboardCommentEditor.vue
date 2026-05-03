<template>
  <div class="whiteboard-comment-editor">
    <RichTextEditor
      ref="editor"
      :key="resetKey"
      v-model="message"
      :mentionable-users="mentionableUsers"
      :editable="!loading"
      :placeholder="placeholder"
      :enable-rich-text-formatting="false"
      :enter-stop-edit="true"
      @stop-edit="onPost"
    />
    <div class="whiteboard-comment-editor__actions">
      <button
        type="button"
        class="whiteboard-comment-editor__cancel"
        :class="{ 'whiteboard-comment-editor__btn--loading': loading }"
        :disabled="loading"
        @click="$emit('cancelled')"
      >
        {{ $t('action.cancel') }}
      </button>
      <button
        type="button"
        class="whiteboard-comment-editor__post"
        :class="{ 'whiteboard-comment-editor__btn--loading': loading }"
        :disabled="!isValid || loading"
        @click="onPost"
      >
        <span v-if="loading" class="whiteboard-comment-editor__spinner" />
        {{ submitLabel || $t('whiteboardComments.post') }}
      </button>
    </div>
  </div>
</template>

<script>
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor'

const EMPTY_DOC = { type: 'doc', content: [{ type: 'paragraph' }] }

export default {
  name: 'WhiteboardCommentEditor',
  components: { RichTextEditor },
  props: {
    initialMessage: { type: Object, default: () => EMPTY_DOC },
    loading: { type: Boolean, default: false },
    placeholder: { type: String, default: '' },
    submitLabel: { type: String, default: '' },
    // The whiteboard's own workspace, looked up by id at the page
    // level. Carries `.users` for the mention picker — read directly
    // off the prop so we don't depend on `workspace/getSelected`,
    // which can flip while the user navigates between workspaces.
    workspace: { type: Object, required: true },
    autofocus: { type: Boolean, default: false },
  },
  emits: ['posted', 'cancelled'],
  data() {
    return {
      message: this.initialMessage,
      // Bumped on `clear()` to force a fresh `RichTextEditor` mount.
      // The editor watches `modelValue` and calls `setContent`, but
      // we've seen edge cases where the underlying ProseMirror state
      // keeps the just-posted content for replies even after the
      // watcher fires. Remounting via :key is a reliable reset.
      resetKey: 0,
    }
  },
  computed: {
    mentionableUsers() {
      return this.workspace?.users || []
    },
    isValid() {
      // ProseMirror considers an empty doc valid; we extra-gate against
      // posting nothing at all.
      const text = JSON.stringify(this.message || {})
      return /"text"\s*:/.test(text) || /"type"\s*:\s*"mention"/.test(text)
    },
  },
  mounted() {
    if (this.autofocus) {
      // Wait for the underlying TipTap instance to be ready before
      // calling `.focus()` on it; on a freshly-mounted popup the
      // editor's commands aren't available synchronously.
      this.$nextTick(() => {
        this.$refs.editor?.focus?.()
      })
    }
  },
  methods: {
    onPost() {
      if (!this.isValid || this.loading) return
      this.$emit('posted', this.message)
    },
    /** Reset the editor to an empty document. Called by the parent
     *  after a successful post so the next reply / new comment starts
     *  fresh, while keeping the popup open. */
    clear() {
      const empty = JSON.parse(JSON.stringify(EMPTY_DOC))
      // Wipe the live TipTap editor synchronously via its imperative
      // command. The post-button path was relying on the `:key`-based
      // remount alone, but the Enter key path doesn't visually clear —
      // TipTap's onUpdate hook fires once more after `stop-edit`
      // bubbles up, which beats Vue's re-render and re-pushes the
      // typed content into `modelValue`. Calling `clearContent` first
      // wins that race regardless of the post path.
      const editorRef = this.$refs.editor
      if (editorRef?.editor) {
        editorRef.editor.commands.clearContent(true)
      }
      this.message = empty
      // Belt-and-suspenders: force a fresh `RichTextEditor` mount.
      this.resetKey += 1
      this.$nextTick(() => {
        this.$refs.editor?.focus?.()
      })
    },
  },
}
</script>

<style lang="scss" scoped>
.whiteboard-comment-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
  // No internal horizontal padding — alignment with neighbouring
  // comment bodies is the parent container's responsibility (the
  // thread's editor wrapper, or the comment item's own padding when
  // editing). Adding padding here doubled-up inside the item's
  // padding and shifted the edit indent past the preview indent.
}
.whiteboard-comment-editor__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.whiteboard-comment-editor__cancel,
.whiteboard-comment-editor__post {
  background: #fff;
  border: 1px solid #d0d4d8;
  border-radius: 4px;
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  &.whiteboard-comment-editor__btn--loading {
    cursor: progress;
  }
}
.whiteboard-comment-editor__post {
  background: #5b8ff9;
  color: #fff;
  border-color: #5b8ff9;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.whiteboard-comment-editor__spinner {
  width: 12px;
  height: 12px;
  border: 2px solid #fff;
  border-top-color: transparent;
  border-radius: 50%;
  animation: whiteboard-comment-editor-spin 0.6s linear infinite;
}
@keyframes whiteboard-comment-editor-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
