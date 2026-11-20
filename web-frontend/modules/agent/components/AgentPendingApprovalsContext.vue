<template>
  <Context
    ref="context"
    class="agent-pending-approvals"
    role="dialog"
    tabindex="-1"
    :aria-label="$t('agent.approvalsWaiting', { count: agent.pending_count })"
    @keydown.esc.stop.prevent="dismiss"
    @shown="open"
    @hidden="close"
  >
    <div
      v-if="loadingPage && !page && !error"
      class="loading"
      role="status"
      :aria-label="$t('agent.loadingApprovals')"
    />
    <p v-if="page && !error && !replies.length">
      {{ $t('agent.pendingApprovalsEmpty') }}
    </p>
    <section
      v-for="reply in replies"
      :key="reply.uuid"
      class="agent-pending-approvals__reply"
    >
      <AgentApprovalCard
        :items="items(reply)"
        :disabled="!canDecide"
        :can-always-allow="canAlwaysAllow"
        :deciding="decidingReplies.has(reply.uuid)"
        compact
        @decide="(decisions, options) => review(reply, decisions, options)"
      >
        <template #title>
          <button
            type="button"
            class="agent-pending-approvals__conversation"
            :title="reply.conversation.title || $t('agent.newConversation')"
            @click="openConversation(reply.conversation)"
          >
            <i class="iconoir-chat-bubble-empty" aria-hidden="true" />
            <span class="agent-pending-approvals__conversation-name">{{
              reply.conversation.title || $t('agent.newConversation')
            }}</span>
          </button>
        </template>
      </AgentApprovalCard>
    </section>
    <Alert v-if="error" type="error">
      {{ $t('agent.pendingApprovalsLoadError') }}
      <template #actions
        ><Button :loading="loadingPage !== null" @click="load(failedPage)">{{
          $t('action.retry')
        }}</Button></template
      >
    </Alert>
    <Button
      v-if="hasMore && !error"
      :loading="loadingPage > 1"
      :disabled="loadingPage !== null"
      @click="load(page + 1)"
      >{{ $t('agent.moreApprovals') }}</Button
    >
  </Context>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useNuxtApp } from '#app'
import { useI18n } from 'vue-i18n'
import AgentApprovalCard from '@baserow/modules/agent/components/AgentApprovalCard'
import AgentApplicationService from '@baserow/modules/agent/services/agentApplication'
import {
  approvalItem,
  pendingApprovals,
} from '@baserow/modules/agent/utils/replies'

const props = defineProps({
  agent: { type: Object, required: true },
  canDecide: Boolean,
  canAlwaysAllow: Boolean,
  decidingReplies: { type: Set, required: true },
  decide: { type: Function, required: true },
})
const emit = defineEmits(['open-conversation'])
const { $client, $registry } = useNuxtApp()
const { t } = useI18n()
const context = ref(null)
const replies = ref([])
const page = ref(0)
const hasMore = ref(false)
const loadingPage = ref(null)
const error = ref(false)
const failedPage = ref(1)
let request = 0
let opened = false

function items(reply) {
  const steps = new Map(reply.steps.map((step) => [step.id, step]))
  return reply.approvals.map((approval) =>
    approvalItem(
      steps.get(approval.step_id) || { tool: approval.tool, status: 'waiting' },
      approval,
      $registry,
      t
    )
  )
}

async function load(number = 1) {
  const current = ++request
  const panel = context.value?.getTeleportedElement?.()
  const hadFocus = panel?.contains(document.activeElement)
  loadingPage.value = number
  try {
    const service = AgentApplicationService($client)
    let lastPage = number
    let { data } = await service.getPendingApprovals(props.agent.id, lastPage)
    if (current !== request) return
    const results = [...data.results]
    // A decision can shift every later page by one. Keep the visible rows
    // until the same number of pages has been reconciled.
    while (number === 1 && data.next && lastPage < page.value) {
      const response = await service.getPendingApprovals(
        props.agent.id,
        ++lastPage
      )
      if (current !== request) return
      data = response.data
      results.push(...data.results)
    }
    const rows = number === 1 ? results : [...replies.value, ...results]
    replies.value = [
      ...new Map(rows.map((reply) => [reply.uuid, reply])).values(),
    ]
    page.value = lastPage
    error.value = false
    hasMore.value = !!data.next
  } catch {
    if (current === request) {
      error.value = true
      failedPage.value = number
    }
  } finally {
    if (current === request) {
      loadingPage.value = null
      await nextTick()
      if (opened && hadFocus && document.activeElement === document.body) {
        panel.focus({ preventScroll: true })
      }
    }
  }
}

async function open() {
  opened = true
  load()
  await nextTick()
  if (opened)
    context.value?.getTeleportedElement?.()?.focus({ preventScroll: true })
}

function dismiss() {
  const opener = context.value.opener
  context.value.hide()
  opener?.focus()
}

function close() {
  opened = false
  request++
  loadingPage.value = null
  error.value = false
  replies.value = []
  hasMore.value = false
  page.value = 0
}

function openConversation(conversation) {
  context.value.hide()
  emit('open-conversation', conversation)
}

async function review(reply, decisions, options) {
  const updated = await props.decide(
    reply,
    decisions,
    options,
    reply.conversation.uuid
  )
  if (!opened) return
  if (updated) {
    const approvals = pendingApprovals(updated)
    replies.value = replies.value.flatMap((item) => {
      if (item.uuid !== updated.uuid) return [item]
      return approvals.length
        ? [{ ...item, approvals, steps: updated.steps }]
        : []
    })
  }
  // A removed reply changes page offsets. Supersede any older list read too.
  if (!updated || hasMore.value || loadingPage.value !== null) await load()
}

watch(
  () => props.agent.pending_count,
  () => {
    if (opened) load()
  }
)
onBeforeUnmount(close)
defineExpose({
  toggle: (target) => context.value.toggle(target, 'bottom', 'left', 4),
})
</script>
