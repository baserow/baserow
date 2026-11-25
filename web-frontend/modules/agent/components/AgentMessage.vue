<template>
  <ChatMessage
    v-if="message.role === MESSAGE_ROLE.TRIGGER"
    class="chat-message--trigger"
  >
    <AgentTriggerStartCard
      :content="message.content"
      :trigger-type="triggerType"
      :trigger-name="triggerName"
    />
    <template #actions>
      <ChatMessageFooter
        :text="message.content"
        :timestamp="message.created_on"
      />
    </template>
  </ChatMessage>
  <ChatMessage
    v-else
    :own="ownMessage || fromVisitor"
    :class="{ 'chat-message--steps': entries.length }"
  >
    <template v-for="entry in entries" :key="entry.key">
      <AgentQuestionCard
        v-if="entry.questionItem"
        :item="entry.questionItem"
        :read-only="!canApprove"
        :disabled="!canDecide"
        :deciding="deciding"
        @decide="(decisions) => $emit('decide', decisions)"
      />
      <AgentApprovalCard
        v-else-if="entry.items"
        :items="entry.items"
        :disabled="!canDecide"
        :can-always-allow="canAlwaysAllow"
        :deciding="deciding"
        :started-by-channel="startedByChannel"
        @decide="(decisions, options) => $emit('decide', decisions, options)"
      />
      <ChatStepGroup
        v-else
        :title="entry.group.title"
        :status="entry.group.status"
        :description="entry.group.description"
        :links="entry.group.links"
        :changes-data="entry.group.changesData"
        :failure-hint="entry.group.failureHint"
        :lines="entry.group.lines"
        :input="entry.group.input"
        :item-errors="entry.group.itemErrors || []"
      />
    </template>
    <div
      v-if="fromPerson && !ownMessage"
      class="chat-message__bubble chat-message__bubble--peer"
    >
      <div class="chat-message__sender">{{ senderName }}</div>
      <div class="chat-message__text">{{ message.content }}</div>
    </div>
    <div v-else-if="fromPerson" class="chat-message__bubble">
      {{ message.content }}
    </div>
    <div
      v-else-if="shown.content || (shown.replying && !entries.length)"
      class="chat-message__bubble"
      aria-live="polite"
      :aria-busy="shown.replying"
    >
      <ChatMarkdown v-if="shown.content" :content="shown.content" agent-links />
      <ChatTyping
        v-if="
          !shown.content ||
          (shown.replying && entries.length && !hasRunningStep)
        "
      />
    </div>
    <div
      v-if="outcome.error"
      class="chat-message__bubble chat-message__bubble--error"
    >
      {{ $t(outcome.error) }}
    </div>
    <div v-if="outcome.note" class="chat-message__note">
      {{ $t(outcome.note, outcome.noteParams || {}) }}
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
import { groupToolSteps } from '@baserow/modules/core/toolPresentationTypes'
import {
  isTerminalStatus,
  STEP_STATUS,
} from '@baserow/modules/core/chatRuns/constants'
import AgentApprovalCard from '@baserow/modules/agent/components/AgentApprovalCard'
import AgentQuestionCard from '@baserow/modules/agent/components/AgentQuestionCard'
import AgentTriggerStartCard from '@baserow/modules/agent/components/AgentTriggerStartCard'
import {
  approvalItem,
  isQuestionStep,
  replyOutcome,
} from '@baserow/modules/agent/utils/replies'

const NO_STEPS = []
const NO_APPROVALS = []

const props = defineProps({
  message: { type: Object, required: true },
  /** Whether the viewer has the permission to approve held steps. */
  canApprove: { type: Boolean, default: false },
  /** Whether the viewer may approve or reject the reply's held steps. */
  canDecide: { type: Boolean, default: false },
  /** Whether the viewer may also turn off Ask first for the held tools. */
  canAlwaysAllow: { type: Boolean, default: false },
  /** A decision about this reply's held steps is being saved. */
  deciding: { type: Boolean, default: false },
  /** The service type key of the trigger that started the conversation. */
  triggerType: { type: String, default: null },
  /** The current name of the trigger that started the conversation. */
  triggerName: { type: String, default: null },
  /** Whether the message is part of an example, sent by nobody of this instance. */
  example: { type: Boolean, default: false },
  /** Whether a visitor started the conversation through a channel. */
  startedByChannel: { type: Boolean, default: false },
})
defineEmits(['decide'])

const store = useStore()
const { $registry } = useNuxtApp()
const { t } = useI18n()
const fromVisitor = computed(() => props.message.role === MESSAGE_ROLE.VISITOR)
const fromPerson = computed(
  () => fromVisitor.value || props.message.role === MESSAGE_ROLE.USER
)
// Others write in a shared conversation too, so only the viewer's own are theirs.
const ownMessage = computed(
  () =>
    props.message.role === MESSAGE_ROLE.USER &&
    props.message.sender?.id === store.getters['auth/getUserId']
)
const senderName = computed(() =>
  fromVisitor.value
    ? t('agent.visitor')
    : props.message.sender?.name ||
      t(props.example ? 'agent.exampleSender' : 'agent.deletedSender')
)
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

function questionItem(step, approval) {
  return {
    id: approval.id,
    status: approval.status,
    question: step.input?.question ?? '',
    answer: approval.answer ?? '',
  }
}

/** Questions get their own card so a pause's batch decisions never include one. */
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
    if (isQuestionStep(step)) {
      addOthers()
      entries.push({
        key: `question-${approval.id}`,
        questionItem: questionItem(step, approval),
      })
      continue
    }
    if (!cardOfPause.has(approval.pause)) {
      addOthers()
      const card = { key: `pause-${approval.pause}`, items: [] }
      cardOfPause.set(approval.pause, card)
      entries.push(card)
    }
    cardOfPause
      .get(approval.pause)
      .items.push(approvalItem(step, approval, $registry, t))
  }
  addOthers()
  return entries
}

// Stable arrays let text deltas skip rebuilding and re-rendering the steps.
const steps = computed(() =>
  fromPerson.value || !Array.isArray(shown.value.steps)
    ? NO_STEPS
    : shown.value.steps
)
const approvals = computed(() =>
  fromPerson.value || !Array.isArray(shown.value.approvals)
    ? NO_APPROVALS
    : shown.value.approvals
)
const hasRunningStep = computed(() =>
  steps.value.some((step) => step.status === STEP_STATUS.RUNNING)
)
const groupedEntries = computed(() => stepEntries(steps.value, approvals.value))
const awaitingText = computed(
  () => shown.value.replying && !shown.value.content
)
const entries = computed(() => {
  const items = groupedEntries.value
  const last = items.at(-1)?.group
  // A model may spend time choosing its next workspace read after the last one
  // finishes. Keep the group active until text, a different step or a terminal event.
  if (
    last?.lines.length &&
    last.status === STEP_STATUS.DONE &&
    awaitingText.value
  ) {
    return [
      ...items.slice(0, -1),
      {
        ...items.at(-1),
        group: {
          ...last,
          status: STEP_STATUS.RUNNING,
          title: t('toolPresentation.workspaceRunning'),
        },
      },
    ]
  }
  return items
})
const outcome = computed(() =>
  replyOutcome(shown.value, store.getters['auth/getUserId'])
)
</script>
