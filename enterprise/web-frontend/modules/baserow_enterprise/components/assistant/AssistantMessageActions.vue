<template>
  <div class="assistant__actions">
    <div class="assistant__actions-header">
      <template v-if="message.can_submit_feedback">
        <button
          v-if="!message.human_sentiment || message.human_sentiment === 'LIKE'"
          ref="thumbUpButton"
          class="assistant__feedback-button assistant__feedback-button--thumb-up"
          :class="{
            'assistant__feedback-button--active':
              message.human_sentiment === 'LIKE',
          }"
          @click="handleThumbsUp"
        >
          <i class="iconoir-thumbs-up"></i>
        </button>

        <button
          v-if="
            !message.human_sentiment || message.human_sentiment === 'DISLIKE'
          "
          ref="thumbDownButton"
          class="assistant__feedback-button assistant__feedback-button--thumb-down"
          :class="{
            'assistant__feedback-button--active':
              message.human_sentiment === 'DISLIKE',
          }"
          @click="handleThumbsDown"
        >
          <i class="iconoir-thumbs-down"></i>
        </button>

        <button
          class="assistant__feedback-button assistant__feedback-button--copy"
          @click="handleCopy"
        >
          <i class="iconoir-copy"></i>
        </button>
      </template>
    </div>

    <!-- Additional user feedback context for the thumb down button -->
    <Context
      ref="feedbackContext"
      class="assistant__feedback-context"
      @shown="$nextTick($refs.feedbackTextarea.focus)"
    >
      <FormGroup
        class="assistant__feedback-context-content"
        small-label
        :label="$t('assistantMessageActions.feedbackContextTitle')"
      >
        <FormTextarea
          ref="feedbackTextarea"
          v-model="feedbackText"
          :placeholder="
            $t('assistantMessageActions.feedbackContextPlaceholder')
          "
          :rows="3"
          size="small"
          @keydown.enter="handleEnterKey"
        />
        <div class="assistant__feedback-context-actions">
          <Button
            type="secondary"
            size="small"
            @click="$refs.feedbackContext.hide()"
          >
            {{ $t('action.cancel') }}
          </Button>
          <Button
            type="primary"
            size="small"
            :disabled="!feedbackText || feedbackText.trim().length === 0"
            @click="handleSubmitFeedback"
          >
            {{ $t('action.submit') }}
          </Button>
        </div>
      </FormGroup>
    </Context>
  </div>
</template>

<script>
import Context from '@baserow/modules/core/components/Context'
import FormTextarea from '@baserow/modules/core/components/FormTextarea'
import { mapActions } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'AssistantMessageActions',
  components: {
    Context,
    FormTextarea,
  },
  props: {
    message: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      feedbackType: null, // 'LIKE' | 'DISLIKE' | null
      feedbackText: '',
    }
  },

  methods: {
    ...mapActions({
      _submitFeedback: 'assistant/submitFeedback',
    }),
    async submitFeedback(payload) {
      try {
        return await this._submitFeedback(payload)
      } catch (error) {
        notifyIf(error)
      }
    },
    handleThumbsUp() {
      // Toggle positive feedback
      this.submitFeedback({
        messageId: this.message.id,
        sentiment: this.message.human_sentiment === 'LIKE' ? null : 'LIKE',
      })
    },

    handleThumbsDown() {
      if (
        this.message.human_sentiment !== 'DISLIKE' &&
        !this.$refs.feedbackContext.isOpen()
      ) {
        this.submitFeedback({
          messageId: this.message.id,
          sentiment: 'DISLIKE',
        })

        this.feedbackText = ''
        // Open feedback context to enter text
        this.$refs.feedbackContext.show(
          this.$refs.thumbDownButton,
          'bottom',
          'left',
          4
        )
      } else {
        // If already open, or already disliked, toggle off
        this.submitFeedback({
          messageId: this.message.id,
          sentiment: null,
        })
        this.$refs.feedbackContext.hide()
      }
    },

    handleEnterKey($event) {
      if (
        $event.shiftKey ||
        !this.feedbackText ||
        this.feedbackText.trim().length === 0
      ) {
        return // Allow new line
      }

      $event.preventDefault()
      this.handleSubmitFeedback()
    },

    handleSubmitFeedback() {
      this.submitFeedback({
        messageId: this.message.id,
        sentiment: 'DISLIKE',
        feedback: this.feedbackText.trim(),
      })
      this.$refs.feedbackContext.hide()
    },

    handleCopy() {
      const content = this.message.content || ''
      navigator.clipboard
        .writeText(content)
        .then(() => {
          this.$store.dispatch('toast/info', {
            title: this.$t('assistantMessageActions.copiedToClipboard'),
            message: this.$t('assistantMessageActions.copiedContentToast'),
          })
        })
        .catch(() => {
          this.$store.dispatch('toast/error', {
            title: this.$t('assistantMessageActions.copyFailed'),
          })
        })
    },
  },
}
</script>
