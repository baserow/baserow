<template>
  <div class="agent-configuration" :style="{ width: `${width}px` }">
    <div
      class="agent-configuration__resize-handle"
      @mousedown.prevent="startResize"
    ></div>
    <div class="agent-configuration__header">
      <div class="agent-configuration__title">
        {{ $t('agentConfiguration.title') }}
      </div>
      <a
        class="agent-configuration__close"
        :title="$t('agentConfiguration.close')"
        @click="$emit('close')"
      >
        <i class="iconoir-cancel"></i>
      </a>
    </div>
    <div class="agent-configuration__body">
      <div class="agent-configuration__section">
        <div class="agent-configuration__section-title">
          {{ $t('agentConfiguration.trigger') }}
        </div>
        <AgentTriggerSection
          :application="application"
          :read-only="!canUpdateTrigger"
        />
      </div>
      <div class="agent-configuration__section">
        <div class="agent-configuration__section-title">
          {{ $t('agentConfiguration.instructions') }}
        </div>
        <template v-if="agent">
          <FormGroup
            small-label
            :label="$t('agentConfiguration.nameLabel')"
            class="margin-bottom-2"
          >
            <FormInput
              v-model="name"
              :disabled="!canUpdateAgent"
              @input="onInput"
            ></FormInput>
          </FormGroup>
          <FormGroup
            small-label
            :label="$t('agentConfiguration.instructionsLabel')"
          >
            <FormTextarea
              v-model="instructions"
              :rows="8"
              :disabled="!canUpdateAgent"
              :placeholder="$t('agentConfiguration.instructionsPlaceholder')"
              @input="onInput"
            ></FormTextarea>
          </FormGroup>
        </template>
      </div>
      <div class="agent-configuration__section">
        <div class="agent-configuration__section-title">
          {{ $t('agentConfiguration.model') }}
        </div>
        <AgentModelSection
          v-if="agent"
          :application="application"
          :read-only="!canUpdateAgent"
        />
      </div>
      <div class="agent-configuration__section">
        <div class="agent-configuration__section-title">
          {{ $t('agentConfiguration.workspaceAccess') }}
        </div>
        <AgentWorkspaceAccessSection
          :application="application"
          :read-only="!canUpdateAgent"
        />
      </div>
      <div class="agent-configuration__section">
        <div class="agent-configuration__section-title">
          {{ $t('agentConfiguration.tools') }}
        </div>
        <AgentToolsSection :application="application" />
      </div>
      <div class="agent-configuration__section">
        <div class="agent-configuration__section-title">
          {{ $t('agentConfiguration.chatChannels') }}
        </div>
        <AgentChatChannelsSection :application="application" />
      </div>
      <div class="agent-configuration__section">
        <a
          class="agent-configuration__section-toggle"
          @click="memoryExpanded = !memoryExpanded"
        >
          <i
            class="agent-configuration__section-chevron iconoir-nav-arrow-right"
            :class="{
              'agent-configuration__section-chevron--expanded': memoryExpanded,
            }"
          ></i>
          {{ $t('agentConfiguration.memory') }}
        </a>
        <div class="agent-configuration__section-description">
          {{ $t('agentConfiguration.memoryDescription') }}
        </div>
        <div v-if="memoryExpanded" class="agent-configuration__section-body">
          <div
            v-if="memoryBlank"
            class="agent-configuration__placeholder"
            :class="{ 'margin-bottom-2': canUpdateAgent }"
          >
            {{ $t('agentConfiguration.memoryEmpty') }}
          </div>
          <FormTextarea
            v-if="canUpdateAgent || !memoryBlank"
            v-model="memory"
            :rows="6"
            :disabled="!canUpdateAgent"
            @input="onMemoryInput"
          ></FormTextarea>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, computed, watch, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#imports'
import debounce from 'lodash/debounce'
import { notifyIf } from '@baserow/modules/core/utils/error'

import AgentModelSection from '@baserow_enterprise/components/agentApplication/AgentModelSection'
import AgentWorkspaceAccessSection from '@baserow_enterprise/components/agentApplication/AgentWorkspaceAccessSection'
import AgentTriggerSection from '@baserow_enterprise/components/agentApplication/AgentTriggerSection'
import AgentToolsSection from '@baserow_enterprise/components/agentApplication/AgentToolsSection'
import AgentChatChannelsSection from '@baserow_enterprise/components/agentApplication/AgentChatChannelsSection'

const SEEDED_FIELDS = ['name', 'instructions', 'memory']
const WIDTH_STORAGE_KEY = 'agentConfigurationPanelWidth'
const DEFAULT_WIDTH = 480
const MIN_WIDTH = 360
const MAX_WIDTH = 720

export default defineComponent({
  name: 'AgentConfigurationPanel',
  components: {
    AgentModelSection,
    AgentWorkspaceAccessSection,
    AgentTriggerSection,
    AgentToolsSection,
    AgentChatChannelsSection,
  },
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  emits: ['close'],
  setup(props) {
    const store = useStore()
    const { $hasPermission } = useNuxtApp()

    const agent = computed(() => store.getters['agentApplication/getAgent'])

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

    const fields = {
      name: ref(agent.value?.name || ''),
      instructions: ref(agent.value?.instructions || ''),
      memory: ref(agent.value?.memory || ''),
    }
    // The value each field was last seeded with, so a remote agent update
    // (e.g. the agent configuring itself via chat, or its remember tool
    // rewriting the memory) only re-seeds fields the user hasn't diverged
    // from, instead of stomping an active edit.
    const seeded = {
      name: agent.value?.name || '',
      instructions: agent.value?.instructions || '',
      memory: agent.value?.memory || '',
    }

    // Deep watch, because agent updates mutate the same store object.
    watch(
      agent,
      (newAgent) => {
        for (const field of SEEDED_FIELDS) {
          const newValue = newAgent?.[field] || ''
          if (fields[field].value === seeded[field]) {
            fields[field].value = newValue
          }
          seeded[field] = newValue
        }
      },
      { deep: true }
    )

    const save = async () => {
      if (!agent.value || !canUpdateAgent.value) {
        return
      }
      // Never PATCH values that already match the agent, otherwise the
      // realtime echo of our own save could re-trigger the cycle.
      if (
        fields.name.value === (agent.value.name || '') &&
        fields.instructions.value === (agent.value.instructions || '')
      ) {
        return
      }
      try {
        await store.dispatch('agentApplication/update', {
          agentId: agent.value.id,
          values: {
            name: fields.name.value,
            instructions: fields.instructions.value,
          },
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    }

    const debouncedSave = debounce(save, 1000)

    const onInput = () => {
      debouncedSave()
    }

    const memoryExpanded = ref(false)
    const memoryBlank = computed(() => fields.memory.value.trim() === '')
    const saveMemory = async () => {
      if (!agent.value || !canUpdateAgent.value) {
        return
      }
      // Never PATCH a value that already matches the agent, otherwise the
      // realtime echo of our own save could re-trigger the cycle.
      if (fields.memory.value === (agent.value.memory || '')) {
        return
      }
      try {
        await store.dispatch('agentApplication/update', {
          agentId: agent.value.id,
          values: { memory: fields.memory.value },
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    }
    const debouncedSaveMemory = debounce(saveMemory, 1000)
    const onMemoryInput = () => {
      debouncedSaveMemory()
    }

    onBeforeUnmount(() => {
      debouncedSave.flush()
      debouncedSaveMemory.flush()
      stopResize()
    })

    return {
      agent,
      canUpdateAgent,
      canUpdateTrigger,
      width,
      startResize,
      name: fields.name,
      instructions: fields.instructions,
      memory: fields.memory,
      memoryExpanded,
      memoryBlank,
      onInput,
      onMemoryInput,
    }
  },
})
</script>
