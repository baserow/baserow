<template>
  <Context ref="context" class="agent-pending-approvals" @shown="fetch">
    <div class="agent-pending-approvals__body">
      <div v-if="loading" class="agent-pending-approvals__loading">
        <div class="loading"></div>
      </div>
      <div
        v-else-if="approvals.length === 0"
        class="agent-pending-approvals__empty"
      >
        {{ $t('agentPendingApprovals.empty') }}
      </div>
      <template v-else>
        <div
          v-for="approval in approvals"
          :key="approval.id"
          class="agent-pending-approvals__item"
          :title="$t('agentPendingApprovals.openConversation')"
          @click="openConversation(approval)"
        >
          <div class="agent-pending-approvals__item-content">
            <div class="agent-pending-approvals__item-tool">
              {{ humanToolName(approval.tool_name) }}
            </div>
            <div class="agent-pending-approvals__item-chat">
              {{ approval.chat_title || $t('agentPendingApprovals.untitled') }}
            </div>
            <div
              v-if="argsPreview(approval)"
              class="agent-pending-approvals__item-args"
            >
              {{ argsPreview(approval) }}
            </div>
          </div>
          <div v-if="canDecide" class="agent-pending-approvals__item-buttons">
            <Button
              size="small"
              type="secondary"
              :disabled="deciding"
              @click.stop="decide(approval, true)"
            >
              {{ $t('agentPendingApprovals.approve') }}
            </Button>
            <Button
              size="small"
              type="danger"
              :disabled="deciding"
              @click.stop="decide(approval, false)"
            >
              {{ $t('agentPendingApprovals.reject') }}
            </Button>
          </div>
        </div>
      </template>
    </div>
  </Context>
</template>

<script>
import { defineComponent, ref, computed } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#imports'
import { notifyIf } from '@baserow/modules/core/utils/error'
import AgentApplicationService from '@baserow_enterprise/services/agentApplication'

// Longer args previews add noise without being readable in a compact row; the
// full args stay visible on the approval card in the conversation itself.
const ARGS_PREVIEW_LENGTH = 120

export default defineComponent({
  name: 'AgentPendingApprovalsContext',
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  emits: ['open-conversation'],
  setup(props, { emit }) {
    const store = useStore()
    const { $client, $hasPermission } = useNuxtApp()

    const context = ref(null)
    const approvals = ref([])
    const loading = ref(false)
    const deciding = ref(false)

    const canDecide = computed(() =>
      $hasPermission(
        'agent_application.run_chat',
        props.application,
        props.application.workspace.id
      )
    )

    const toggle = (...args) => context.value.toggle(...args)
    const hide = () => context.value.hide()

    const fetch = async () => {
      loading.value = true
      try {
        const { data } = await AgentApplicationService(
          $client
        ).getPendingApprovals(props.application.id)
        approvals.value = data
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        loading.value = false
      }
    }

    const humanToolName = (name) => (name || '').replace(/_/g, ' ')

    const argsPreview = (approval) => {
      if (!approval.tool_args || Object.keys(approval.tool_args).length === 0) {
        return ''
      }
      const preview = JSON.stringify(approval.tool_args)
      return preview.length > ARGS_PREVIEW_LENGTH
        ? `${preview.slice(0, ARGS_PREVIEW_LENGTH)}…`
        : preview
    }

    const removeLocally = (approval) => {
      approvals.value = approvals.value.filter(
        (item) => item.id !== approval.id
      )
      // The websocket event corrects the count shortly after, but decrement
      // optimistically so the header button reacts immediately.
      store.dispatch('application/forceUpdate', {
        application: props.application,
        data: {
          pending_approvals_count: Math.max(
            0,
            (props.application.pending_approvals_count || 0) - 1
          ),
        },
      })
    }

    const decide = async (approval, approved) => {
      if (deciding.value) {
        return
      }
      deciding.value = true
      try {
        await AgentApplicationService($client).decideApprovals(
          approval.chat_uuid,
          [{ id: approval.id, approved }]
        )
        removeLocally(approval)
      } catch (error) {
        if (
          error.handler &&
          error.handler.code === 'ERROR_AGENT_TOOL_APPROVAL_DOES_NOT_EXIST'
        ) {
          // Another collaborator already decided this approval; refresh the
          // list so the stale row disappears.
          error.handler.handled()
          await fetch()
        } else {
          notifyIf(error, 'application')
        }
      } finally {
        deciding.value = false
      }
    }

    const openConversation = (approval) => {
      emit('open-conversation', approval.chat_uuid)
      hide()
    }

    return {
      context,
      approvals,
      loading,
      deciding,
      canDecide,
      toggle,
      hide,
      fetch,
      humanToolName,
      argsPreview,
      decide,
      openConversation,
    }
  },
})
</script>
