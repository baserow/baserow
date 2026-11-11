<template>
  <div
    ref="card"
    class="agent-approval"
    role="group"
    tabindex="-1"
    :aria-labelledby="titleId"
  >
    <div class="agent-approval__header">
      <i class="iconoir-shield-check agent-approval__icon" aria-hidden="true" />
      <span :id="titleId" class="agent-approval__title">
        {{
          pending.length
            ? $t('agent.approvalRequest', { name: agent.name })
            : $t('agent.approvalReviewed')
        }}
      </span>
      <Button
        v-if="pending.length && canAlwaysAllow"
        type="secondary"
        size="small"
        class="agent-approval__always-allow"
        :disabled="locked"
        :title="alwaysAllowTitle"
        @click="approve(pending, { alwaysAllow: true })"
      >
        {{ alwaysAllowLabel }}
      </Button>
      <div v-if="pending.length" class="agent-approval__actions">
        <Button
          type="secondary"
          size="small"
          :disabled="locked"
          @click="askToReject(pending, $event)"
        >
          {{ $t(pending.length > 1 ? 'agent.rejectAll' : 'agent.reject') }}
        </Button>
        <Button
          ref="headerApprove"
          type="primary"
          size="small"
          :disabled="locked"
          @click="approve(pending)"
        >
          {{ $t(pending.length > 1 ? 'agent.approveAll' : 'agent.approve') }}
        </Button>
      </div>
      <div v-else class="agent-approval__summary">
        <span v-if="approvedCount">
          {{ $t('agent.approvalApprovedCount', { count: approvedCount }) }}
        </span>
        <span v-if="rejectedCount">
          {{ $t('agent.approvalRejectedCount', { count: rejectedCount }) }}
        </span>
      </div>
    </div>
    <ul class="agent-approval__items">
      <li v-for="item in items" :key="item.id" class="agent-approval__item">
        <div class="agent-approval__item-head">
          <span :id="itemTitleId(item)" class="agent-approval__item-title">
            {{ item.title }}
          </span>
          <template v-if="item.status === APPROVAL_STATUS.APPROVED">
            <span v-if="outcomeIcon(item)" class="agent-approval__step-status">
              <i :class="outcomeIcon(item)" aria-hidden="true" />
              {{ outcomeLabel(item, $t) }}
            </span>
            <span
              class="agent-approval__decision agent-approval__decision--approved"
            >
              <i class="iconoir-check-circle" aria-hidden="true" />
              {{ $t('agent.approved') }}
            </span>
          </template>
          <span
            v-else-if="item.status === APPROVAL_STATUS.REJECTED"
            class="agent-approval__decision agent-approval__decision--rejected"
          >
            <i class="iconoir-prohibition" aria-hidden="true" />
            {{ $t('agent.rejected') }}
          </span>
          <div
            v-else-if="pending.length > 1"
            class="agent-approval__item-actions"
          >
            <Button
              type="secondary"
              size="small"
              :disabled="locked"
              :aria-describedby="itemTitleId(item)"
              @click="askToReject([item], $event)"
            >
              {{ $t('agent.reject') }}
            </Button>
            <Button
              :ref="(button) => setItemApprove(item, button)"
              type="primary"
              size="small"
              :disabled="locked"
              :aria-describedby="itemTitleId(item)"
              @click="approve([item])"
            >
              {{ $t('agent.approve') }}
            </Button>
          </div>
        </div>
        <p v-if="item.failureHint" class="agent-approval__item-note">
          {{ item.failureHint }}
        </p>
        <p
          v-for="(error, index) in item.itemErrors"
          :key="index"
          class="agent-approval__item-note"
        >
          {{ error.item ? `${error.item}: ${error.message}` : error.message }}
        </p>
        <div class="agent-approval__item-meta">
          <button
            v-if="item.input"
            type="button"
            class="agent-approval__details-toggle"
            :aria-expanded="expanded.has(item.id)"
            :aria-controls="detailsId(item)"
            @click="toggleDetails(item)"
          >
            <i
              :class="
                expanded.has(item.id)
                  ? 'iconoir-nav-arrow-down'
                  : 'iconoir-nav-arrow-right'
              "
              aria-hidden="true"
            />
            {{
              $t(
                expanded.has(item.id)
                  ? 'agent.hideDetails'
                  : 'agent.showDetails'
              )
            }}
          </button>
          <code class="agent-approval__tool">{{ item.tool }}</code>
        </div>
        <ChatToolInput
          v-if="item.input && expanded.has(item.id)"
          :id="detailsId(item)"
          class="agent-approval__input"
          :input="item.input"
        />
      </li>
    </ul>
    <div class="agent-approval__announcement" role="status">
      <span v-if="announcement" :key="announcement.id">
        {{ $t(announcement.textKey) }}
      </span>
    </div>
    <AgentRejectModal ref="rejectModal" @reject="reject" />
  </div>
</template>

<script setup>
import { computed, inject, reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useNuxtApp } from '#app'
import { agentToolLabel } from '@baserow/modules/agent/agentTools'
import AgentRejectModal from '@baserow/modules/agent/components/AgentRejectModal'
import ChatToolInput from '@baserow/modules/core/components/chat/ChatToolInput'
import { STEP_STATUS } from '@baserow/modules/core/chatRuns/constants'
import { stepStatusLabel } from '@baserow/modules/core/toolPresentationTypes'
import { APPROVAL_STATUS } from '@baserow/modules/agent/utils/replies'

/** Held steps for the conversation's owner to approve or reject. */
const props = defineProps({
  /** `{id, status, stepStatus, changesData, partial, tool, title, input, failureHint}`. */
  items: { type: Array, required: true },
  /** The viewer may not decide. */
  disabled: { type: Boolean, default: false },
  /** The viewer may also turn off Ask first for these steps' tools. */
  canAlwaysAllow: { type: Boolean, default: false },
  /** A decision about these steps is being saved. */
  deciding: { type: Boolean, default: false },
})
const emit = defineEmits(['decide'])

const agent = inject('agentApplication')
const titleId = useId()
const card = ref(null)
const headerApprove = ref(null)
const itemApproves = new Map()
const rejectModal = ref(null)
const expanded = reactive(new Set())
const announcement = ref(null)
let rejecting = []
let submitted = null

const locked = computed(() => props.disabled || props.deciding)
const pending = computed(() =>
  props.items.filter((item) => item.status === APPROVAL_STATUS.PENDING)
)
const { $registry } = useNuxtApp()
const { locale, t } = useI18n()
const pendingToolNames = computed(() =>
  [...new Set(pending.value.map((item) => item.tool))].map((tool) =>
    agentToolLabel(tool, $registry, t)
  )
)
const alwaysAllowLabel = computed(() =>
  pendingToolNames.value.length > 1
    ? t('agent.alwaysAllowAllPendingTools')
    : t('agent.alwaysAllowTools', { tools: pendingToolNames.value[0] })
)
const alwaysAllowTitle = computed(() =>
  pendingToolNames.value.length > 1
    ? new Intl.ListFormat(locale.value, { type: 'conjunction' }).format(
        pendingToolNames.value
      )
    : null
)
const countOf = (status) =>
  props.items.filter((item) => item.status === status).length
const approvedCount = computed(() => countOf(APPROVAL_STATUS.APPROVED))
const rejectedCount = computed(() => countOf(APPROVAL_STATUS.REJECTED))
const OUTCOME_ICONS = {
  [STEP_STATUS.FAILED]: 'iconoir-warning-triangle',
  [STEP_STATUS.STOPPED]: 'iconoir-minus-circle',
}
const outcomeIcon = (item) =>
  item.partial ? 'iconoir-warning-circle' : OUTCOME_ICONS[item.stepStatus]
const outcomeLabel = ({ stepStatus, changesData, partial }, t) =>
  stepStatusLabel({ status: stepStatus, changesData, partial }, t)
const itemTitleId = (item) => `${titleId}-${item.id}-title`
const detailsId = (item) => `${titleId}-${item.id}-details`

function toggleDetails(item) {
  if (expanded.has(item.id)) expanded.delete(item.id)
  else expanded.add(item.id)
}

function setItemApprove(item, button) {
  if (button) itemApproves.set(item.id, button)
  else itemApproves.delete(item.id)
}

/** Send the decisions, remembered until their save ends. */
function decide(decisions, options) {
  submitted = {
    ids: decisions.map(({ id }) => id),
    approved: decisions[0].approved,
  }
  emit('decide', decisions, options)
}

function approve(items, options) {
  if (locked.value) return
  decide(
    items.map((item) => ({ id: item.id, approved: true })),
    options
  )
}

function askToReject(items, event) {
  rejecting = items
  rejectModal.value.show(
    items.map((item) => item.title),
    event.currentTarget
  )
}

function reject(reason) {
  if (locked.value) return
  decide(
    rejecting.map((item) => ({
      id: item.id,
      approved: false,
      ...(reason ? { reason } : {}),
    }))
  )
}

/** Announce a saved decision and move focus off its removed buttons. */
function settle() {
  const { ids, approved } = submitted
  submitted = null
  if (pending.value.some((item) => ids.includes(item.id))) return
  // A new id replaces the node, so a repeated outcome is announced again.
  announcement.value = {
    id: (announcement.value?.id ?? 0) + 1,
    textKey: approved ? 'agent.approved' : 'agent.rejected',
  }
  const active = document.activeElement
  if (active && active !== document.body && !card.value.contains(active)) {
    return
  }
  const next =
    pending.value.length > 1
      ? itemApproves.get(pending.value[0].id)
      : headerApprove.value
  ;(next || card.value).focus()
}

watch(
  () => props.deciding,
  (deciding) => {
    if (!deciding && submitted) settle()
  },
  { flush: 'post' }
)
</script>
