<template>
  <div
    class="whiteboard-comment-item"
    :class="{ 'whiteboard-comment-item--loading': loadingState }"
  >
    <div class="whiteboard-comment-item__header">
      <span class="whiteboard-comment-item__author">
        {{ comment.first_name || $t('whiteboardComments.unknownAuthor') }}
      </span>
      <span class="whiteboard-comment-item__time">
        {{ formattedTime }}
        <span v-if="comment.edited"
          >({{ $t('whiteboardComments.edited') }})</span
        >
      </span>
      <button
        v-if="canEdit && !editing"
        class="whiteboard-comment-item__menu-button"
        type="button"
        :disabled="!!loadingState"
        @click="editing = true"
      >
        ✎
      </button>
      <button
        v-if="canEdit && !editing"
        class="whiteboard-comment-item__menu-button"
        type="button"
        :disabled="!!loadingState"
        @click="onDelete"
      >
        ✕
      </button>
    </div>
    <div v-if="!editing" class="whiteboard-comment-item__body">
      <WhiteboardCommentReadOnly :message="comment.message" />
    </div>
    <WhiteboardCommentEditor
      v-else
      :initial-message="comment.message"
      :loading="loadingState === 'updating'"
      :placeholder="$t('whiteboardComments.placeholderEdit')"
      :workspace-id="workspaceId"
      :submit-label="$t('whiteboardComments.save')"
      :autofocus="true"
      @posted="onSave"
      @cancelled="editing = false"
    />
  </div>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import WhiteboardCommentEditor from '@baserow/modules/whiteboard/components/comments/WhiteboardCommentEditor.vue'
import WhiteboardCommentReadOnly from '@baserow/modules/whiteboard/components/comments/WhiteboardCommentReadOnly.vue'
import moment from '@baserow/modules/core/moment'

export default {
  name: 'WhiteboardCommentItem',
  components: { WhiteboardCommentEditor, WhiteboardCommentReadOnly },
  props: {
    comment: { type: Object, required: true },
    readOnly: { type: Boolean, default: false },
  },
  data() {
    return { editing: false }
  },
  computed: {
    workspaceId() {
      return this.$store.getters['application/getSelected']?.workspace?.id
    },
    canEdit() {
      if (this.readOnly) return false
      const me = this.$store.getters['auth/getUserObject']
      return me?.id === this.comment.user_id
    },
    loadingState() {
      return this.$store.getters['whiteboardComments/getCommentLoadingState'](
        this.comment.id
      )
    },
    formattedTime() {
      return moment(this.comment.created_on).fromNow()
    },
  },
  methods: {
    async onSave(message) {
      try {
        await this.$store.dispatch('whiteboardComments/updateComment', {
          commentId: this.comment.id,
          message,
        })
      } catch (error) {
        // Keep edit mode open so the user doesn't lose what they typed.
        notifyIf(error, 'application')
        return
      }
      this.editing = false
    },
    async onDelete() {
      if (!window.confirm(this.$t('whiteboardComments.confirmDelete'))) return
      try {
        await this.$store.dispatch('whiteboardComments/deleteComment', {
          commentId: this.comment.id,
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
  },
}
</script>

<style lang="scss" scoped>
.whiteboard-comment-item {
  padding: 8px 12px;
  border-bottom: 1px solid #f4f4f4;
  font-size: 13px;
  &:last-child {
    border-bottom: none;
  }
  &--loading {
    opacity: 0.7;
  }
}
.whiteboard-comment-item__header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.whiteboard-comment-item__author {
  font-weight: 600;
}
.whiteboard-comment-item__time {
  color: #888;
  font-size: 11px;
  flex: 1;
}
.whiteboard-comment-item__menu-button {
  background: none;
  border: none;
  cursor: pointer;
  color: #888;
  padding: 0 4px;
  &:hover {
    color: #333;
  }
  &:disabled {
    opacity: 0.5;
    cursor: progress;
  }
}
.whiteboard-comment-item__body {
  word-break: break-word;
}
</style>
