<template>
  <header class="layout__col-2-1 header header--space-between">
    <div class="agent-page__header-title">
      <i class="agent-page__header-icon baserow-icon-agent"></i>
      <span class="agent-page__header-name">
        {{ agent?.name || application.name }}
      </span>
      <ul class="header__filter agent-page__header-approvals">
        <li class="header__filter-item">
          <a
            ref="approvalsButton"
            class="header__filter-link agent-page__header-approvals-link"
            :class="{
              'agent-page__header-approvals-link--pending':
                pendingApprovalsCount > 0,
            }"
            @click="toggleApprovalsContext"
          >
            <i
              class="header__filter-icon iconoir-check-circle agent-page__header-approvals-icon"
            ></i>
            <span class="header__filter-name">{{
              $t('agentHeader.approvalsWaiting', {
                count: pendingApprovalsCount,
              })
            }}</span>
          </a>
        </li>
      </ul>
      <AgentPendingApprovalsContext
        ref="approvalsContext"
        :application="application"
        @open-conversation="$emit('open-conversation', $event)"
      />
    </div>
    <div class="header__right">
      <span class="agent-page__header-status">
        <Badge :color="activeValue ? 'green' : 'neutral'" indicator rounded>
          {{
            activeValue ? $t('agentHeader.active') : $t('agentHeader.paused')
          }}
        </Badge>
        <SwitchInput
          small
          :value="activeValue"
          :disabled="!canUpdateApplication"
          :title="$t('agentHeader.activeTitle')"
          @input="toggleActive"
        ></SwitchInput>
      </span>
      <div class="header__buttons header__buttons--with-separator">
        <span class="agent-page__header-last-run">
          {{
            application.last_run_on
              ? $t('agentHeader.lastRun', { time: lastRun })
              : $t('agentHeader.neverRan')
          }}
        </span>
        <Button
          v-if="canRunOnce"
          type="secondary"
          icon="iconoir-play"
          :loading="runningOnce"
          @click="$emit('run-once')"
        >
          {{ $t('agentHeader.runOnce') }}
        </Button>
        <ButtonIcon
          icon="iconoir-settings"
          :active="configurationOpen"
          :title="$t('agentHeader.configure')"
          @click="$emit('toggle-configuration')"
        ></ButtonIcon>
      </div>
    </div>
  </header>
</template>

<script>
import { defineComponent, computed, ref } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#imports'
import moment from '@baserow/modules/core/moment'
import { notifyIf } from '@baserow/modules/core/utils/error'
import AgentPendingApprovalsContext from '@baserow_enterprise/components/agentApplication/AgentPendingApprovalsContext'

export default defineComponent({
  name: 'AgentHeader',
  components: { AgentPendingApprovalsContext },
  props: {
    application: {
      type: Object,
      required: true,
    },
    configurationOpen: {
      type: Boolean,
      required: false,
      default: false,
    },
    runningOnce: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['toggle-configuration', 'open-conversation', 'run-once'],
  setup(props) {
    const store = useStore()
    const { $hasPermission } = useNuxtApp()

    const agent = computed(() => store.getters['agentApplication/getAgent'])
    const triggers = computed(
      () => store.getters['agentApplication/getTriggers']
    )

    // Driven by the application object in the core store, so the workspace
    // wide `agent_pending_approvals_updated` websocket event updates it live.
    const pendingApprovalsCount = computed(
      () => props.application.pending_approvals_count || 0
    )

    const approvalsButton = ref(null)
    const approvalsContext = ref(null)
    const toggleApprovalsContext = () => {
      approvalsContext.value.toggle(approvalsButton.value, 'bottom', 'left', 4)
    }

    const canRunChat = computed(() =>
      $hasPermission(
        'agent_application.run_chat',
        props.application,
        props.application.workspace.id
      )
    )
    const canRunOnce = computed(
      () =>
        canRunChat.value && triggers.value.some((trigger) => trigger.enabled)
    )
    const lastRun = computed(() =>
      moment(props.application.last_run_on).calendar()
    )

    const canUpdateApplication = computed(() =>
      $hasPermission(
        'application.update',
        props.application,
        props.application.workspace.id
      )
    )

    // The switch must flip immediately and stay interactive while the request
    // is in flight. `pendingActive` holds the latest intent during a sync, so
    // rapid toggling serializes into follow-up requests (latest intent wins)
    // instead of racing them; a failure clears it, reverting the switch to the
    // server state.
    const pendingActive = ref(null)
    const activeValue = computed(() =>
      pendingActive.value === null
        ? Boolean(props.application.active)
        : pendingActive.value
    )
    const toggleActive = async (active) => {
      const syncing = pendingActive.value !== null
      pendingActive.value = active
      if (syncing) {
        return
      }
      try {
        while (pendingActive.value !== Boolean(props.application.active)) {
          await store.dispatch('application/update', {
            application: props.application,
            values: { active: pendingActive.value },
          })
        }
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        pendingActive.value = null
      }
    }

    return {
      agent,
      canRunOnce,
      lastRun,
      canUpdateApplication,
      activeValue,
      toggleActive,
      pendingApprovalsCount,
      approvalsButton,
      approvalsContext,
      toggleApprovalsContext,
    }
  },
})
</script>
