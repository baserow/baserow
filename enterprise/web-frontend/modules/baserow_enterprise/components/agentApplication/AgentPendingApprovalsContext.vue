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
          class="agent-tool-approvals__header agent-pending-approvals__header"
        >
          <i class="iconoir-shield-check agent-tool-approvals__header-icon"></i>
          <span class="agent-tool-approvals__header-title">
            {{ $t('agentPendingApprovals.title', { count: approvals.length }) }}
          </span>
        </div>
        <div
          v-for="approval in approvals"
          :key="approval.id"
          class="agent-tool-approvals__item"
        >
          <div class="agent-tool-approvals__item-body">
            <div class="agent-tool-approvals__tool-name">
              {{ humanToolName(approval.tool_name) }}
            </div>
            <a
              class="agent-pending-approvals__chat"
              :title="$t('agentPendingApprovals.openConversation')"
              @click.prevent="openConversation(approval)"
            >
              <i class="iconoir-chat-bubble-empty"></i>
              <span>{{
                approval.chat_title || $t('agentPendingApprovals.untitled')
              }}</span>
            </a>
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
          <div v-if="canDecide" class="agent-tool-approvals__item-side">
            <div class="agent-tool-approvals__item-actions">
              <Button
                size="small"
                type="secondary"
                :disabled="deciding"
                :loading="isDeciding(approval, false)"
                @click="decide(approval, false)"
              >
                {{ $t('agentPendingApprovals.reject') }}
              </Button>
              <Button
                size="small"
                type="primary"
                :disabled="deciding"
                :loading="isDeciding(approval, true)"
                @click="decide(approval, true)"
              >
                {{ $t('agentPendingApprovals.approve') }}
              </Button>
            </div>
          </div>
        </div>
      </template>
    </div>
  </Context>
</template>

<script>
import { defineComponent, ref, computed, reactive } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#imports'
import { notifyIf } from '@baserow/modules/core/utils/error'
import AgentApplicationService from '@baserow_enterprise/services/agentApplication'
import { summarizeToolArgs } from '@baserow_enterprise/utils/agentChatEvents'

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

    const humanToolName = (name) =>
      store.getters['agentApplication/getToolLabel'](name)

    const summary = (approval) => summarizeToolArgs(approval.tool_args)
    const formatArgs = (approval) =>
      JSON.stringify(approval.tool_args ?? {}, null, 2)
    const expandedArgs = reactive({})
    const toggleDetails = (approval) => {
      expandedArgs[approval.id] = !expandedArgs[approval.id]
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

    const decidingKey = ref(null)
    const isDeciding = (approval, approved) =>
      deciding.value && decidingKey.value === `${approval.id}-${approved}`
    const decide = async (approval, approved) => {
      if (deciding.value) {
        return
      }
      deciding.value = true
      decidingKey.value = `${approval.id}-${approved}`
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
      isDeciding,
      context,
      approvals,
      loading,
      deciding,
      canDecide,
      toggle,
      hide,
      fetch,
      humanToolName,
      summary,
      formatArgs,
      expandedArgs,
      toggleDetails,
      decide,
      openConversation,
    }
  },
})
</script>
