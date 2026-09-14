<template>
  <div
    class="agent-tool-approvals"
    :class="{ 'agent-tool-approvals--pending': hasPending }"
  >
    <div class="agent-tool-approvals__header">
      <i class="iconoir-shield-check agent-tool-approvals__header-icon"></i>
      <span class="agent-tool-approvals__header-title">
        {{
          hasPending
            ? $t('agentToolApprovals.asksForApproval', { name: agentName })
            : $t('agentToolApprovals.reviewedByYou')
        }}
      </span>
      <div
        v-if="hasPending && canDecide"
        class="agent-tool-approvals__header-actions"
      >
        <Checkbox
          v-if="canChangeTools"
          v-model="dontAskAgain"
          :disabled="disabled"
        >
          {{ $t('agentToolApprovals.dontAskAgain') }}
        </Checkbox>
        <Button
          size="small"
          type="secondary"
          :disabled="disabled"
          :loading="isDeciding('reject-all')"
          @click="rejectAll"
        >
          {{ $t('agentToolApprovals.rejectAll') }}
        </Button>
        <Button
          size="small"
          type="primary"
          :disabled="disabled"
          :loading="isDeciding('approve-all')"
          @click="approveAll"
        >
          {{ $t('agentToolApprovals.approveAll') }}
        </Button>
      </div>
      <span
        v-else-if="!hasPending"
        class="agent-tool-approvals__header-summary"
      >
        {{ decidedSummary }}
      </span>
    </div>
    <div
      v-for="approval in approvals"
      :key="approval.id"
      class="agent-tool-approvals__item"
    >
      <div class="agent-tool-approvals__item-body">
        <div class="agent-tool-approvals__tool-name">
          {{ toolLabel(approval.tool_name) }}
        </div>
        <div v-if="summary(approval)" class="agent-tool-approvals__summary">
          {{ summary(approval) }}
        </div>
        <div class="agent-tool-approvals__details">
          <a
            class="agent-tool-approvals__details-toggle"
            @click.prevent="toggleDetails(approval)"
          >
            <i
              class="iconoir-nav-arrow-right agent-tool-approvals__details-chevron"
              :class="{
                'agent-tool-approvals__details-chevron--expanded':
                  expandedArgs[approval.id],
              }"
            ></i>
            {{
              expandedArgs[approval.id]
                ? $t('agentToolApprovals.hideDetails')
                : $t('agentToolApprovals.showDetails')
            }}
          </a>
          <code class="agent-tool-approvals__details-id">{{
            approval.tool_name
          }}</code>
        </div>
        <pre
          v-if="expandedArgs[approval.id]"
          class="agent-tool-approvals__args"
          >{{ formatArgs(approval) }}</pre
        >
      </div>
      <div class="agent-tool-approvals__item-side">
        <template v-if="approval.status === 'pending'">
          <div v-if="canDecide" class="agent-tool-approvals__item-actions">
            <Button
              size="small"
              type="secondary"
              :disabled="disabled"
              :loading="isDeciding(`reject-${approval.id}`)"
              @click="startReject(approval)"
            >
              {{ $t('agentToolApprovals.reject') }}
            </Button>
            <Button
              size="small"
              type="primary"
              :disabled="disabled"
              :loading="isDeciding(`approve-${approval.id}`)"
              @click="approve(approval)"
            >
              {{ $t('agentToolApprovals.approve') }}
            </Button>
          </div>
          <span v-else class="agent-tool-approvals__pending-label">
            {{ $t('agentToolApprovals.pending') }}
          </span>
        </template>
        <span
          v-else
          class="agent-tool-approvals__decision"
          :class="`agent-tool-approvals__decision--${approval.status}`"
        >
          <i
            class="agent-tool-approvals__decision-icon"
            :class="
              approval.status === 'approved'
                ? 'iconoir-check-circle'
                : 'iconoir-cancel'
            "
          ></i>
          <span class="agent-tool-approvals__decision-text">
            {{
              approval.status === 'approved'
                ? $t('agentToolApprovals.approved')
                : $t('agentToolApprovals.rejected')
            }}<template v-if="approval.reason">
              · {{ approval.reason }}</template
            >
          </span>
        </span>
      </div>
    </div>
    <AgentRejectApprovalModal ref="rejectModal" @reject="confirmReject" />
  </div>
</template>

<script>
import { defineComponent, ref, reactive, computed, watch } from 'vue'
import { useI18n } from '#imports'
import { summarizeToolArgs } from '@baserow_enterprise/utils/agentChatEvents'
import AgentRejectApprovalModal from '@baserow_enterprise/components/agentApplication/AgentRejectApprovalModal'

export default defineComponent({
  name: 'AgentToolApprovals',
  components: { AgentRejectApprovalModal },
  props: {
    approvals: {
      type: Array,
      required: true,
    },
    canDecide: {
      type: Boolean,
      required: true,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    agentName: {
      type: String,
      required: false,
      default: '',
    },
    canChangeTools: {
      type: Boolean,
      required: false,
      default: false,
    },
    toolLabel: {
      type: Function,
      required: false,
      default: (name) => name,
    },
  },
  emits: ['decide'],
  setup(props, { emit }) {
    const { t } = useI18n()
    const rejectModal = ref(null)
    const dontAskAgain = ref(false)
    const expandedArgs = reactive({})

    const pendingApprovals = computed(() =>
      props.approvals.filter((approval) => approval.status === 'pending')
    )
    const hasPending = computed(() => pendingApprovals.value.length > 0)

    const decidedSummary = computed(() => {
      const approved = props.approvals.filter(
        (approval) => approval.status === 'approved'
      ).length
      const rejected = props.approvals.filter(
        (approval) => approval.status === 'rejected'
      ).length
      const parts = []
      if (approved > 0) {
        parts.push(t('agentToolApprovals.approvedCount', { count: approved }))
      }
      if (rejected > 0) {
        parts.push(t('agentToolApprovals.rejectedCount', { count: rejected }))
      }
      return parts.join(' · ')
    })

    const summary = (approval) => summarizeToolArgs(approval.tool_args)
    const formatArgs = (approval) =>
      JSON.stringify(approval.tool_args ?? {}, null, 2)
    const toggleDetails = (approval) => {
      expandedArgs[approval.id] = !expandedArgs[approval.id]
    }

    // Which button was clicked, so that one spins while the parent's
    // `disabled` (the request being in flight) is true.
    const decidingAction = ref(null)
    watch(
      () => props.disabled,
      (disabled) => {
        if (!disabled) {
          decidingAction.value = null
        }
      }
    )
    const isDeciding = (action) =>
      props.disabled && decidingAction.value === action
    const decide = (action, decisions) => {
      decidingAction.value = action
      emit('decide', { decisions, dontAskAgain: dontAskAgain.value })
    }
    const approve = (approval) =>
      decide(`approve-${approval.id}`, [{ id: approval.id, approved: true }])
    const startReject = (approval) => {
      rejectModal.value.show(approval, props.toolLabel(approval.tool_name))
    }
    const confirmReject = ({ approval, reason }) => {
      const decision = { id: approval.id, approved: false }
      if (reason !== '') {
        decision.reason = reason
      }
      decide(`reject-${approval.id}`, [decision])
    }
    const approveAll = () =>
      decide(
        'approve-all',
        pendingApprovals.value.map((approval) => ({
          id: approval.id,
          approved: true,
        }))
      )
    const rejectAll = () =>
      decide(
        'reject-all',
        pendingApprovals.value.map((approval) => ({
          id: approval.id,
          approved: false,
        }))
      )

    return {
      isDeciding,
      rejectModal,
      dontAskAgain,
      expandedArgs,
      hasPending,
      decidedSummary,
      summary,
      formatArgs,
      toggleDetails,
      approve,
      startReject,
      confirmReject,
      approveAll,
      rejectAll,
    }
  },
})
</script>
