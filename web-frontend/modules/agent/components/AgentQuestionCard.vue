<template>
  <div
    ref="card"
    class="agent-question"
    role="group"
    tabindex="-1"
    :aria-labelledby="titleId"
    :aria-describedby="decided ? decisionId : undefined"
  >
    <div class="agent-question__header">
      <i
        class="iconoir-chat-bubble-question agent-question__icon"
        aria-hidden="true"
      />
      <span :id="titleId" class="agent-question__title">
        {{ $t('agent.questionTitle', { name: agent.name }) }}
      </span>
    </div>
    <div class="agent-question__body">
      <p class="agent-question__question">{{ item.question }}</p>
      <template v-if="!decided">
        <p v-if="readOnly" class="agent-question__hint">
          {{ $t('agent.questionReadOnly') }}
        </p>
        <template v-else>
          <FormGroup
            :label="$t('agent.questionAnswerLabel')"
            small-label
            required
          >
            <FormTextarea
              v-model="answer"
              auto-expandable
              :min-rows="2"
              :max-rows="10"
              :maxlength="ASK_PERSON_ANSWER_MAX_LENGTH"
              :placeholder="$t('agent.questionAnswerPlaceholder')"
              :aria-label="$t('agent.questionAnswerLabel')"
              :disabled="locked"
            />
          </FormGroup>
          <p :id="hintId" class="agent-question__hint">
            {{ $t('agent.questionDismissHint') }}
          </p>
          <div class="agent-question__actions">
            <Button
              type="secondary"
              size="small"
              :disabled="locked"
              :aria-describedby="hintId"
              @click="dismiss"
            >
              {{ $t('agent.questionDismiss') }}
            </Button>
            <Button
              type="primary"
              size="small"
              :disabled="locked || !trimmedAnswer"
              @click="send"
            >
              {{ $t('agent.questionSend') }}
            </Button>
          </div>
        </template>
      </template>
      <div v-else :id="decisionId">
        <span
          class="agent-question__decision"
          :class="`agent-question__decision--${item.status}`"
        >
          <i
            :class="answered ? 'iconoir-check-circle' : 'iconoir-prohibition'"
            aria-hidden="true"
          />
          {{
            $t(answered ? 'agent.questionAnswered' : 'agent.questionDismissed')
          }}
        </span>
        <p v-if="answered && item.answer" class="agent-question__answer">
          {{ item.answer }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, ref, useId, watch } from 'vue'
import { APPROVAL_STATUS } from '@baserow/modules/agent/utils/replies'
import { ASK_PERSON_ANSWER_MAX_LENGTH } from '@baserow/modules/agent/constants'

/** A question a triggered run asks, for a person to answer or dismiss. */
const props = defineProps({
  /** `{id, status, question, answer}`. */
  item: { type: Object, required: true },
  /** The viewer lacks the permission to decide, so only reads the question. */
  readOnly: { type: Boolean, default: false },
  /** The viewer may not decide right now, for example while the agent loads. */
  disabled: { type: Boolean, default: false },
  /** A decision about this question is being saved. */
  deciding: { type: Boolean, default: false },
})
const emit = defineEmits(['decide'])

const agent = inject('agentApplication')
const titleId = useId()
const hintId = useId()
const decisionId = useId()
const card = ref(null)
const answer = ref('')
let submitted = false

const locked = computed(() => props.disabled || props.deciding)
const trimmedAnswer = computed(() => answer.value.trim())
const decided = computed(() => props.item.status !== APPROVAL_STATUS.PENDING)
const answered = computed(() => props.item.status === APPROVAL_STATUS.APPROVED)

function decide(decision) {
  if (locked.value) return
  submitted = true
  emit('decide', [{ id: props.item.id, ...decision }])
}

function send() {
  if (trimmedAnswer.value) {
    decide({ approved: true, answer: trimmedAnswer.value })
  }
}

function dismiss() {
  decide({ approved: false })
}

// The answered card drops its buttons, so focus would otherwise fall to the page.
watch(
  () => props.deciding,
  (deciding) => {
    if (deciding || !submitted) return
    submitted = false
    const active = document.activeElement
    if (
      decided.value &&
      (!active || active === document.body || card.value.contains(active))
    ) {
      card.value.focus()
    }
  },
  { flush: 'post' }
)
</script>
