<template>
  <Modal ref="modal" small>
    <template #content>
      <h2 class="box__title">{{ $t('agent.toolPermissions') }}</h2>
      <p class="agent-tool-permissions__description">
        {{ $t('agent.toolPermissionsDescription', { name: agentName }) }}
      </p>
      <div
        v-for="group in groups"
        :key="group.type"
        class="agent-tool-permissions__group"
      >
        <div class="agent-tool-permissions__group-name">
          <i :class="group.icon"></i>
          {{ group.label }}
        </div>
        <p class="agent-tool-permissions__summary">
          {{
            $t('agent.toolsAskFirstSummary', {
              on: group.tools.filter((tool) => picked.has(tool.name)).length,
              total: group.tools.length,
              count: group.tools.filter((tool) => askFirst.has(tool.name))
                .length,
            })
          }}
        </p>
        <div
          v-for="kind in kindsOf(group)"
          :key="kind.label"
          class="agent-tool-permissions__list"
        >
          <div class="agent-tool-permissions__list-head">
            <span>{{ kind.label }}</span>
            <div class="agent-tool-permissions__columns">
              <span>{{ $t('agent.toolAllow') }}</span>
              <span>{{ $t('agent.toolAskFirst') }}</span>
            </div>
          </div>
          <div
            v-for="tool in kind.tools"
            :key="tool.name"
            class="agent-tool-permissions__tool"
          >
            <div>
              <div class="agent-tool-permissions__tool-name">
                {{ tool.label }}
              </div>
              <div
                v-if="tool.description"
                class="agent-tool-permissions__tool-description"
              >
                {{ tool.description }}
              </div>
            </div>
            <div class="agent-tool-permissions__columns">
              <Checkbox
                class="agent-tool-permissions__allow"
                :model-value="picked.has(tool.name)"
                :disabled="!editable"
                @update:model-value="allow(tool.name, $event)"
                >{{ tool.label }}</Checkbox
              >
              <Checkbox
                class="agent-tool-permissions__ask-first"
                :model-value="askFirst.has(tool.name)"
                :disabled="!editable || !picked.has(tool.name)"
                @update:model-value="setAskFirst(tool.name, $event)"
                >{{
                  $t('agent.toolAskFirstLabel', { name: tool.label })
                }}</Checkbox
              >
            </div>
          </div>
        </div>
      </div>
      <div class="agent-tool-permissions__actions">
        <Button type="secondary" @click="modal.hide()">
          {{ $t('action.cancel') }}
        </Button>
        <Button type="primary" :disabled="!editable" @click="done">
          {{ $t('agent.toolsDone') }}
        </Button>
      </div>
    </template>
  </Modal>
</template>

<script setup>
import { useNuxtApp } from '#app'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  groupAgentTools,
  nextAskFirst,
} from '@baserow/modules/agent/agentTools'

/** Picks an Agent's tools and which ask first, saved only on Done. */
const props = defineProps({
  availableTools: { type: Array, required: true },
  allowedTools: { type: Array, required: true },
  askFirstTools: { type: Array, required: true },
  agentName: { type: String, required: true },
  editable: { type: Boolean, required: true },
})
const emit = defineEmits(['save'])
const { t } = useI18n()
const { $registry } = useNuxtApp()

const modal = ref(null)
const picked = ref(new Set())
const askFirst = ref(new Set())
const groups = computed(() =>
  groupAgentTools(props.availableTools, $registry, t)
)

function kindsOf(group) {
  return [
    {
      label: t('agent.toolsReads'),
      tools: group.tools.filter((tool) => !tool.changesData),
    },
    {
      label: t('agent.toolsChanges'),
      tools: group.tools.filter((tool) => tool.changesData),
    },
  ].filter((kind) => kind.tools.length)
}

function allow(name, allowed) {
  if (!props.editable) return
  const next = new Set(picked.value)
  if (allowed) next.add(name)
  else next.delete(name)
  askFirst.value = new Set(
    nextAskFirst(props.availableTools, picked.value, askFirst.value, next)
  )
  picked.value = next
}

function setAskFirst(name, value) {
  if (!props.editable || !picked.value.has(name)) return
  const next = new Set(askFirst.value)
  if (value) next.add(name)
  else next.delete(name)
  askFirst.value = next
}

function show() {
  picked.value = new Set(props.allowedTools)
  askFirst.value = new Set(props.askFirstTools)
  modal.value.show()
}

function done() {
  if (!props.editable) return
  const names = props.availableTools.map((tool) => tool.name)
  emit('save', {
    allowed_tools: names.filter((name) => picked.value.has(name)),
    ask_first_tools: names.filter((name) => askFirst.value.has(name)),
  })
  modal.value.hide()
}

defineExpose({ show })
</script>
