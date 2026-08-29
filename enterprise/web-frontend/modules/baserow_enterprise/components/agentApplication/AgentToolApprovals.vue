<template>
  <div class="agent-tool-approvals">
    <div class="agent-tool-approvals__header">
      <i class="iconoir-shield-question agent-tool-approvals__header-icon"></i>
      <span class="agent-tool-approvals__header-title">
        {{ $t('agentToolApprovals.title') }}
      </span>
    </div>
    <div
      v-for="approval in approvals"
      :key="approval.id"
      class="agent-tool-approvals__item"
    >
      <div class="agent-tool-approvals__item-header">
        <span class="agent-tool-approvals__tool-name">
          {{ humanToolName(approval.tool_name) }}
        </span>
        <template v-if="approval.status === 'pending'">
          <template v-if="canDecide">
            <Button
              size="small"
              type="secondary"
              :disabled="disabled"
              @click="approve(approval)"
            >
              {{ $t('agentToolApprovals.approve') }}
            </Button>
            <Button
              size="small"
              type="danger"
              :disabled="disabled"
              @click="startReject(approval)"
            >
              {{ $t('agentToolApprovals.reject') }}
            </Button>
          </template>
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
      <div v-if="hasArgs(approval)" class="agent-tool-approvals__args-wrapper">
        <pre
          class="agent-tool-approvals__args"
          :class="{
            'agent-tool-approvals__args--collapsed': isCollapsed(approval),
          }"
          >{{ formatArgs(approval) }}</pre
        >
        <a
          v-if="isLargeArgs(approval)"
          class="agent-tool-approvals__args-toggle"
          @click.prevent="toggleArgs(approval)"
        >
          {{
            expandedArgs[approval.id]
              ? $t('agentToolApprovals.showLess')
              : $t('agentToolApprovals.showMore')
          }}
        </a>
      </div>
      <div
        v-if="rejectingId === approval.id"
        class="agent-tool-approvals__reason"
      >
        <FormInput
          v-model="rejectReason"
          size="small"
          class="agent-tool-approvals__reason-input"
          :placeholder="$t('agentToolApprovals.reasonPlaceholder')"
          @keydown.enter="confirmReject(approval)"
        ></FormInput>
        <Button
          size="small"
          type="danger"
          :disabled="disabled"
          @click="confirmReject(approval)"
        >
          {{ $t('agentToolApprovals.reject') }}
        </Button>
        <ButtonText @click="cancelReject">
          {{ $t('agentToolApprovals.cancel') }}
        </ButtonText>
      </div>
    </div>
    <div
      v-if="canDecide && pendingApprovals.length > 1"
      class="agent-tool-approvals__footer"
    >
      <Button
        size="small"
        type="secondary"
        :disabled="disabled"
        @click="approveAll"
      >
        {{ $t('agentToolApprovals.approveAll') }}
      </Button>
      <Button
        size="small"
        type="danger"
        :disabled="disabled"
        @click="rejectAll"
      >
        {{ $t('agentToolApprovals.rejectAll') }}
      </Button>
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, reactive, computed } from 'vue'

// Above this rendered size the args preview starts collapsed.
const ARGS_COLLAPSE_LENGTH = 280
const ARGS_COLLAPSE_LINES = 6

export default defineComponent({
  name: 'AgentToolApprovals',
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
  },
  emits: ['decide'],
  setup(props, { emit }) {
    const rejectingId = ref(null)
    const rejectReason = ref('')
    const expandedArgs = reactive({})

    const pendingApprovals = computed(() =>
      props.approvals.filter((approval) => approval.status === 'pending')
    )

    const humanToolName = (name) => (name || '').replace(/_/g, ' ')

    const formatArgs = (approval) =>
      JSON.stringify(approval.tool_args ?? {}, null, 2)

    const hasArgs = (approval) =>
      approval.tool_args && Object.keys(approval.tool_args).length > 0

    const isLargeArgs = (approval) => {
      const formatted = formatArgs(approval)
      return (
        formatted.length > ARGS_COLLAPSE_LENGTH ||
        formatted.split('\n').length > ARGS_COLLAPSE_LINES
      )
    }

    const isCollapsed = (approval) =>
      isLargeArgs(approval) && !expandedArgs[approval.id]

    const toggleArgs = (approval) => {
      expandedArgs[approval.id] = !expandedArgs[approval.id]
    }

    const cancelReject = () => {
      rejectingId.value = null
      rejectReason.value = ''
    }

    const approve = (approval) => {
      if (rejectingId.value === approval.id) {
        cancelReject()
      }
      emit('decide', [{ id: approval.id, approved: true }])
    }

    const startReject = (approval) => {
      rejectingId.value = approval.id
      rejectReason.value = ''
    }

    const confirmReject = (approval) => {
      const reason = rejectReason.value.trim()
      const decision = { id: approval.id, approved: false }
      if (reason !== '') {
        decision.reason = reason
      }
      cancelReject()
      emit('decide', [decision])
    }

    const approveAll = () => {
      cancelReject()
      emit(
        'decide',
        pendingApprovals.value.map((approval) => ({
          id: approval.id,
          approved: true,
        }))
      )
    }

    const rejectAll = () => {
      cancelReject()
      emit(
        'decide',
        pendingApprovals.value.map((approval) => ({
          id: approval.id,
          approved: false,
        }))
      )
    }

    return {
      rejectingId,
      rejectReason,
      expandedArgs,
      pendingApprovals,
      humanToolName,
      formatArgs,
      hasArgs,
      isLargeArgs,
      isCollapsed,
      toggleArgs,
      approve,
      startReject,
      confirmReject,
      cancelReject,
      approveAll,
      rejectAll,
    }
  },
})
</script>
