<template>
  <ChatMessage :own="own" :class="{ 'chat-message--steps': entries.length }">
    <template v-for="entry in entries" :key="entry.key">
      <AgentApprovalCard
        v-if="entry.items"
        :items="entry.items"
        :disabled="!canDecide"
        :deciding="deciding"
        @decide="$emit('decide', $event)"
      />
      <ChatStepGroup
        v-else
        :title="entry.group.title"
        :status="entry.group.status"
        :changes-data="entry.group.changesData"
        :failure-hint="entry.group.failureHint"
        :lines="entry.group.lines"
        :input="entry.group.input"
        :item-errors="entry.group.itemErrors || []"
      />
    </template>
    <div v-if="own" class="chat-message__bubble">{{ message.content }}</div>
    <div
      v-else-if="shown.content || (shown.replying && !toolRunning)"
      class="chat-message__bubble"
      aria-live="polite"
      :aria-busy="shown.replying"
    >
      <ChatTyping v-if="!shown.content" />
      <ChatMarkdown v-else :content="shown.content" />
    </div>
    <div
      v-if="outcome.error"
      class="chat-message__bubble chat-message__bubble--error"
    >
      {{ $t(outcome.error) }}
    </div>
    <div v-if="outcome.note" class="chat-message__note">
      {{ $t(outcome.note) }}
    </div>
    <template v-if="shown.content && !shown.replying" #actions>
      <ChatMessageFooter
        :text="shown.content"
        :timestamp="message.created_on"
      />
    </template>
  </ChatMessage>
</template>

<script setup>
import { MESSAGE_ROLE } from '@baserow/modules/agent/constants'
import { computed } from 'vue'
import { useStore } from 'vuex'
import { useI18n } from 'vue-i18n'
import { useNuxtApp } from '#app'
import ChatMessageFooter from '@baserow/modules/core/components/chat/ChatMessageFooter'
import ChatMarkdown from '@baserow/modules/core/components/chat/ChatMarkdown'
import ChatMessage from '@baserow/modules/core/components/chat/ChatMessage'
import ChatTyping from '@baserow/modules/core/components/chat/ChatTyping'
import ChatStepGroup from '@baserow/modules/core/components/chat/ChatStepGroup'
import {
  groupToolSteps,
  toolActivity,
} from '@baserow/modules/core/toolPresentationTypes'
import {
  isTerminalStatus,
  STEP_STATUS,
} from '@baserow/modules/core/chatRuns/constants'
import AgentApprovalCard from '@baserow/modules/agent/components/AgentApprovalCard'
import { replyOutcome } from '@baserow/modules/agent/utils/replies'

const NO_STEPS = []
const NO_APPROVALS = []

const props = defineProps({
  message: { type: Object, required: true },
  /** Whether the viewer may approve or reject the reply's held steps. */
  canDecide: { type: Boolean, default: false },
  /** A decision about this reply's held steps is being saved. */
  deciding: { type: Boolean, default: false },
})
defineEmits(['decide'])

const store = useStore()
const { $registry } = useNuxtApp()
const { t } = useI18n()
const own = computed(() => props.message.role === MESSAGE_ROLE.USER)
/** The saved message, with each field its unsaved run already wrote. */
const shown = computed(() => {
  const { message } = props
  const follower =
    message.run_id && store.getters['chatRuns/getFollower'](message.run_id)
  // A follower that lost access can't say how the reply ended.
  if (
    !follower ||
    isTerminalStatus(message.status) ||
    (follower.finished && !isTerminalStatus(follower.view.status))
  ) {
    return { ...message, replying: false }
  }
  const { view } = follower
  return {
    ...message,
    content: view.segment >= 0 ? view.text : message.content,
    status: view.status,
    error_code: view.errorCode,
    steps: view.steps?.length ? view.steps : message.steps,
    replying: !follower.finished,
  }
})

function approvalItem(step, approval) {
  const {
    title,
    input,
    failureHint,
    status,
    changesData,
    partial,
    itemErrors,
  } = toolActivity(step, $registry, t)
  return {
    id: approval.id,
    status: approval.status,
    stepStatus: status,
    changesData,
    tool: approval.tool,
    title,
    input,
    failureHint,
    partial,
    itemErrors,
  }
}

/** One card per pause at its first held step; other steps keep core groups. */
function stepEntries(steps, approvals) {
  const approvalOfStep = new Map(
    approvals.map((approval) => [approval.step_id, approval])
  )
  const cardOfPause = new Map()
  const entries = []
  let others = []
  const addOthers = () => {
    entries.push(
      ...groupToolSteps(others, $registry, t).map((group) => ({
        key: group.id,
        group,
      }))
    )
    others = []
  }
  for (const step of steps) {
    const approval = approvalOfStep.get(step?.id)
    if (!approval) {
      others.push(step)
      continue
    }
    if (!cardOfPause.has(approval.pause)) {
      addOthers()
      const card = { key: `pause-${approval.pause}`, items: [] }
      cardOfPause.set(approval.pause, card)
      entries.push(card)
    }
    cardOfPause.get(approval.pause).items.push(approvalItem(step, approval))
  }
  addOthers()
  return entries
}

// Stable arrays let text deltas skip rebuilding and re-rendering the steps.
const steps = computed(() =>
  own.value || !Array.isArray(shown.value.steps) ? NO_STEPS : shown.value.steps
)
const approvals = computed(() =>
  own.value || !Array.isArray(shown.value.approvals)
    ? NO_APPROVALS
    : shown.value.approvals
)
const entries = computed(() => stepEntries(steps.value, approvals.value))
const toolRunning = computed(() =>
  steps.value?.some((step) => step.status === STEP_STATUS.RUNNING)
)
const outcome = computed(() => replyOutcome(shown.value))
</script>
