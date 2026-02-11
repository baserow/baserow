<template>
  <div
    :class="{
      'row-comments__comment--right': ownComment,
      'row-comments__comment--editing': editing,
    }"
    class="row-comments__comment"
  >
    <div class="row-comments__comment-head">
      <div
        class="row-comments__comment-head-details"
        :class="{ 'row-comments__comment-head-details--right': ownComment }"
      >
        <div v-if="!ownComment" class="row-comments__comment-head-initial">
          {{ $filters.nameAbbreviation(firstName) }}
        </div>
        <div class="row-comments__comment-head-name">
          {{ ownComment ? $t('rowComment.you') : firstName }}
        </div>
        <div :title="timeTooltip" class="row-comments__comment-head-time">
          <span>{{ localCreationTime }}</span>
          <span v-if="comment.edited && !comment.trashed">
            ({{ $t('rowComment.edited') }})
          </span>
        </div>
        <a
          v-if="ownComment && !editing && !comment.trashed"
          ref="commentContextLink"
          :class="{ disabled: operationPending }"
          class="row-comments__comment-context"
          @click.prevent="openRowCommentContext"
        >
          <i
            class="baserow-icon-more-horizontal"
            :class="{ pending: operationPending }"
          ></i>
        </a>
        <RowCommentContext
          ref="commentContext"
          :comment="comment"
          :can-edit="canEdit"
          :can-delete="canDelete && !creating"
          @edit="startEdit"
          @delete="deleteComment"
        ></RowCommentContext>
      </div>
    </div>
    <div
      v-if="comment.trashed"
      class="row-comments__comment-text row-comments__comment-text--trashed"
    >
      {{ $t('rowComment.commentTrashed') }}
    </div>
    <div
      v-else
      class="row-comments__comment-text"
      :class="{ 'row-comments__comment-text--editing': editing }"
    >
      <RichTextEditor
        ref="editor"
        v-model="message"
        :editable="editing"
        :mentionable-users="workspace.users"
        :enter-stop-edit="true"
        @stop-edit="stopEdit(true)"
      />
    </div>
    <div v-if="editing" class="row-comments__comment-text-actions">
      <Button type="secondary" :disabled="updating" @click="stopEdit()">
        {{ $t('action.cancel') }}</Button
      >
      <Button type="primary" :disabled="updating" @click="stopEdit(true)">
        {{ $t('action.save') }}</Button
      >
    </div>
  </div>
</template>

<script>
import _ from 'lodash'
import { mapGetters } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { clone } from '@baserow/modules/core/utils/object'
import RowCommentContext from '@baserow_premium/components/row_comments/RowCommentContext'
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor.vue'

import moment from '@baserow/modules/core/moment'

export default {
  name: 'RowComment',
  components: {
    RowCommentContext,
    RichTextEditor,
  },
  props: {
    comment: {
      type: Object,
      required: true,
    },
    workspace: {
      type: Object,
      required: true,
    },
    canEdit: {
      type: Boolean,
      required: true,
    },
    canDelete: {
      type: Boolean,
      required: true,
    },
  },
  emits: ['stop-edit'],
  data() {
    return {
      editing: false,
      updating: false,
      deleting: false,
      message: this.cloneCommentMessage(),
      onClickOutsideHandler: null,
    }
  },
  computed: {
    ...mapGetters({
      userId: 'auth/getUserId',
    }),
    creating() {
      return this.comment.isTemporary
    },
    operationPending() {
      return this.creating || this.updating || this.deleting
    },

    firstName() {
      if (this.comment.user_id === null) {
        return this.$t('rowComment.anonymous')
      }
      return this.comment.first_name
    },
    ownComment() {
      return this.comment.user_id === this.userId
    },
    localCreationTime() {
      return this.getLocalizedMoment(this.comment.created_on).format('LT')
    },
    localCreationDateTime() {
      return this.getLocalizedMoment(this.comment.created_on).format('L LT')
    },
    localUpdatedDateTime() {
      return this.getLocalizedMoment(this.comment.updated_on).format('L LT')
    },
    timeTooltip() {
      if (this.operationPending) {
        if (this.creating) {
          return this.$t('rowComment.creating')
        } else if (this.updating) {
          return this.$t('rowComment.updating')
        } else if (this.deleting) {
          return this.$t('rowComment.deleting')
        }
      }
      let tooltip =
        this.$t('rowComment.created') + `: ${this.localCreationDateTime}`
      if (this.comment.edited) {
        tooltip += `\n${this.$t('rowComment.edited')}:   ${
          this.localUpdatedDateTime
        }`
      }
      return tooltip
    },
  },
  watch: {
    'comment.message': {
      handler(newVal, oldVal) {
        if (!_.isEqual(oldVal, newVal)) {
          this.message = this.cloneCommentMessage()
        }
      },
    },
  },
  beforeUnmount() {
    this.cleanupClickOutside()
  },
  methods: {
    cleanupClickOutside() {
      if (this.onClickOutsideHandler) {
        document.removeEventListener('click', this.onClickOutsideHandler)
        this.onClickOutsideHandler = null
      }
    },
    getLocalizedMoment(timestamp) {
      return moment.utc(timestamp).tz(moment.tz.guess())
    },
    openRowCommentContext() {
      if (!this.operationPending) {
        this.$refs.commentContext.toggle(
          this.$refs.commentContextLink,
          'bottom',
          'right',
          0
        )
      }
    },
    cloneCommentMessage() {
      // Use clone() instead of structuredClone to handle Vue 3 Proxy objects
      return clone(this.comment.message)
    },
    startEdit() {
      this.$refs.commentContext.hide()
      this.editing = true

      this.onClickOutsideHandler = (evt) => {
        if (
          !this.$el.contains(evt.target) &&
          !this.$refs.commentContext.$el.contains(evt.target) &&
          !evt.composedPath().includes(this.$el)
        ) {
          this.stopEdit()
        }
      }

      document.addEventListener('click', this.onClickOutsideHandler)
    },

    async stopEdit(save = false) {
      this.$emit('stop-edit')
      this.editing = false
      this.cleanupClickOutside()

      if (save) {
        await this.updateComment()
      } else {
        this.message = this.cloneCommentMessage()
      }
    },

    async updateComment() {
      if (!this.message) {
        return
      }

      this.updating = true
      try {
        await this.$store.dispatch('row_comments/updateComment', {
          tableId: this.comment.table_id,
          commentId: this.comment.id,
          message: this.message,
        })
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.updating = false
      }
    },
    async deleteComment() {
      this.deleting = true
      this.$refs.commentContext.hide()

      try {
        await this.$store.dispatch('row_comments/deleteComment', {
          tableId: this.comment.table_id,
          rowId: this.comment.row_id,
          commentId: this.comment.id,
        })
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.deleting = false
      }
    },
  },
}
</script>
