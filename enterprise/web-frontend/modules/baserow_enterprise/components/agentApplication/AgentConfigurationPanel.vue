<template>
  <div class="agent-configuration" :style="{ width: `${width}px` }">
    <div
      class="agent-configuration__resize-handle"
      @mousedown.prevent="startResize"
    ></div>
    <AgentConfigurationSubpage
      v-if="activeSection === null"
      :title="$t('agentConfiguration.title')"
      @close="$emit('close')"
    >
      <div class="agent-configuration__rows">
        <AgentConfigurationSectionRow
          v-for="row in rows"
          :key="row.key"
          :icon="row.icon"
          :title="row.title"
          :summary="row.summary"
          @click="$emit('update:section', row.key)"
        />
      </div>
    </AgentConfigurationSubpage>
    <AgentConfigurationSubpage
      v-else
      :title="activeRow.title"
      show-back
      @back="$emit('update:section', null)"
      @close="$emit('close')"
    >
      <AgentInstructionsSection
        v-if="activeSection === 'instructions'"
        :application="application"
        :can-update="canUpdateAgent"
      />
      <AgentTriggerSection
        v-else-if="activeSection === 'triggers'"
        :application="application"
        :read-only="!canUpdateTrigger"
      />
      <AgentAccessSection
        v-else-if="activeSection === 'access'"
        :application="application"
        :read-only="!canUpdateAgent"
      />
      <AgentActionToolsSection
        v-else-if="activeSection === 'actions'"
        :application="application"
      />
      <AgentChatChannelsSection
        v-else-if="activeSection === 'channels'"
        :application="application"
      />
      <AgentMemorySection
        v-else-if="activeSection === 'memory'"
        :application="application"
        :can-update="canUpdateAgent"
      />
      <AgentAgentSettingsSection
        v-else-if="activeSection === 'settings'"
        :application="application"
        :read-only="!canUpdateAgent"
      />
    </AgentConfigurationSubpage>
  </div>
</template>

<script>
import { defineComponent, ref, computed, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp, useI18n } from '#imports'
import { summarizeAccess } from '@baserow_enterprise/utils/agentToolPermissions'

import AgentConfigurationSubpage from '@baserow_enterprise/components/agentApplication/AgentConfigurationSubpage'
import AgentConfigurationSectionRow from '@baserow_enterprise/components/agentApplication/AgentConfigurationSectionRow'
import AgentInstructionsSection from '@baserow_enterprise/components/agentApplication/AgentInstructionsSection'
import AgentTriggerSection from '@baserow_enterprise/components/agentApplication/AgentTriggerSection'
import AgentAccessSection from '@baserow_enterprise/components/agentApplication/AgentAccessSection'
import AgentActionToolsSection from '@baserow_enterprise/components/agentApplication/AgentActionToolsSection'
import AgentChatChannelsSection from '@baserow_enterprise/components/agentApplication/AgentChatChannelsSection'
import AgentMemorySection from '@baserow_enterprise/components/agentApplication/AgentMemorySection'
import AgentAgentSettingsSection from '@baserow_enterprise/components/agentApplication/AgentAgentSettingsSection'

const WIDTH_STORAGE_KEY = 'agentConfigurationPanelWidth'
const DEFAULT_WIDTH = 400
const MIN_WIDTH = 360
const MAX_WIDTH = 720

const firstLine = (text) =>
  (text || '').split('\n').find((line) => line.trim()) || ''

export default defineComponent({
  name: 'AgentConfigurationPanel',
  components: {
    AgentConfigurationSubpage,
    AgentConfigurationSectionRow,
    AgentInstructionsSection,
    AgentTriggerSection,
    AgentAccessSection,
    AgentActionToolsSection,
    AgentChatChannelsSection,
    AgentMemorySection,
    AgentAgentSettingsSection,
  },
  props: {
    application: {
      type: Object,
      required: true,
    },
    // The open section lives in the parent so it survives closing and
    // reopening the panel.
    section: {
      type: String,
      required: false,
      default: null,
    },
  },
  emits: ['close', 'update:section'],
  setup(props) {
    const store = useStore()
    const { $hasPermission, $registry } = useNuxtApp()
    const { t } = useI18n()

    const agent = computed(() => store.getters['agentApplication/getAgent'])
    const triggers = computed(
      () => store.getters['agentApplication/getTriggers']
    )
    const tools = computed(() => store.getters['agentApplication/getTools'])
    const channels = computed(
      () => store.getters['agentApplication/getChannels']
    )
    const catalog = computed(
      () => store.getters['agentApplication/getWorkspaceToolCatalog']
    )
    const workspace = computed(() =>
      store.getters['workspace/get'](props.application.workspace.id)
    )

    const canUpdateAgent = computed(() =>
      $hasPermission(
        'agent_application.update_agent',
        props.application,
        props.application.workspace.id
      )
    )
    const canUpdateTrigger = computed(() =>
      $hasPermission(
        'agent_application.update_trigger',
        props.application,
        props.application.workspace.id
      )
    )

    const nodeTypeName = (serviceType) => {
      try {
        return $registry.get('node', serviceType).name
      } catch {
        return serviceType
      }
    }

    const triggersSummary = computed(() => {
      const enabled = triggers.value.filter((trigger) => trigger.enabled)
      if (enabled.length === 0) {
        return t('agentConfiguration.whenItRunsEmptySummary')
      }
      return enabled
        .map((trigger) => nodeTypeName(trigger.service_type))
        .join(', ')
    })

    const accessSummary = computed(() => {
      const identity = store.getters['agent/get'](
        props.application.agent_identity_id
      )
      const parts = []
      if (identity) {
        const role = (workspace.value?._?.roles || []).find(
          (item) => item.uid === identity.role_uid
        )
        parts.push(role ? `${identity.name} (${role.name})` : identity.name)
      }
      const workspaceTool = tools.value.find(
        (tool) => tool.type === 'workspace'
      )
      if (workspaceTool && catalog.value.length > 0) {
        const counts = summarizeAccess(workspaceTool.config, catalog.value)
        parts.push(
          counts.ask > 0
            ? t('agentConfiguration.accessToolsSummaryAsk', counts)
            : t('agentConfiguration.accessToolsSummary', counts)
        )
      }
      if (tools.value.some((tool) => tool.type === 'web_search')) {
        parts.push(t('agentConfiguration.accessWebSearch'))
      }
      return parts.length > 0
        ? parts.join(' • ')
        : t('agentConfiguration.accessNoTools')
    })

    const actionsSummary = computed(() => {
      const names = tools.value
        .filter((tool) => ['service', 'mcp'].includes(tool.type))
        .map((tool) => tool.name)
        .filter(Boolean)
      return names.length > 0
        ? names.join(', ')
        : t('agentConfiguration.actionToolsEmptySummary')
    })

    const channelsSummary = computed(() => {
      const names = channels.value.map(
        (channel) => channel.name || t('agentChannels.slack')
      )
      return names.length > 0
        ? names.join(', ')
        : t('agentConfiguration.channelsEmptySummary')
    })

    const rows = computed(() => [
      {
        key: 'instructions',
        icon: 'iconoir-page-edit',
        title: t('agentConfiguration.instructions'),
        summary:
          firstLine(agent.value?.instructions) ||
          t('agentConfiguration.instructionsEmptySummary'),
      },
      {
        key: 'triggers',
        icon: 'iconoir-play',
        title: t('agentConfiguration.whenItRuns'),
        summary: triggersSummary.value,
      },
      {
        key: 'access',
        icon: 'iconoir-shield-check',
        title: t('agentConfiguration.accessAndTools'),
        summary: accessSummary.value,
      },
      {
        key: 'actions',
        icon: 'iconoir-flash',
        title: t('agentConfiguration.actionTools'),
        summary: actionsSummary.value,
      },
      {
        key: 'channels',
        icon: 'iconoir-chat-bubble-empty',
        title: t('agentConfiguration.chatChannels'),
        summary: channelsSummary.value,
      },
      {
        key: 'memory',
        icon: 'iconoir-brain',
        title: t('agentConfiguration.memory'),
        summary:
          firstLine(agent.value?.memory) ||
          t('agentConfiguration.memoryEmptySummary'),
      },
      {
        key: 'settings',
        icon: 'iconoir-settings',
        title: t('agentConfiguration.agentSettings'),
        summary: t('agentConfiguration.agentSettingsSummary'),
      },
    ])

    const activeSection = computed(() =>
      rows.value.some((row) => row.key === props.section) ? props.section : null
    )
    const activeRow = computed(() =>
      rows.value.find((row) => row.key === activeSection.value)
    )

    // Resizable width, persisted per browser.
    const readStoredWidth = () => {
      try {
        const stored = parseInt(localStorage.getItem(WIDTH_STORAGE_KEY))
        if (!isNaN(stored)) {
          return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, stored))
        }
      } catch {}
      return DEFAULT_WIDTH
    }
    const width = ref(readStoredWidth())

    let panelRight = 0
    const onResizeMove = (event) => {
      width.value = Math.min(
        MAX_WIDTH,
        Math.max(MIN_WIDTH, panelRight - event.clientX)
      )
    }
    const stopResize = () => {
      window.removeEventListener('mousemove', onResizeMove)
      window.removeEventListener('mouseup', stopResize)
      document.body.classList.remove('agent-configuration-resizing')
      try {
        localStorage.setItem(WIDTH_STORAGE_KEY, `${width.value}`)
      } catch {}
    }
    const startResize = (event) => {
      panelRight = event.target
        .closest('.agent-configuration')
        .getBoundingClientRect().right
      window.addEventListener('mousemove', onResizeMove)
      window.addEventListener('mouseup', stopResize)
      document.body.classList.add('agent-configuration-resizing')
    }

    onBeforeUnmount(() => {
      stopResize()
    })

    return {
      rows,
      activeSection,
      activeRow,
      canUpdateAgent,
      canUpdateTrigger,
      width,
      startResize,
    }
  },
})
</script>
