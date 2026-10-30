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
            $t('agent.toolsSummary', {
              count: group.tools.filter((tool) => picked.has(tool.name)).length,
              total: group.tools.length,
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
            <span>{{ $t('agent.toolAllow') }}</span>
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
            <Checkbox
              class="agent-tool-permissions__allow"
              :model-value="picked.has(tool.name)"
              :disabled="!editable"
              @update:model-value="toggle(tool.name, $event)"
              >{{ tool.label }}</Checkbox
            >
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
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { groupAgentTools } from '@baserow/modules/agent/agentTools'

/** Lets the user pick the tools an Agent may call, saving them only on Done. */
const props = defineProps({
  availableTools: { type: Array, required: true },
  allowedTools: { type: Array, required: true },
  agentName: { type: String, required: true },
  editable: { type: Boolean, required: true },
})
const emit = defineEmits(['save'])
const { t } = useI18n()

const modal = ref(null)
const picked = ref(new Set())
const groups = computed(() => groupAgentTools(props.availableTools, t))

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

function toggle(name, allowed) {
  if (!props.editable) return
  const next = new Set(picked.value)
  if (allowed) next.add(name)
  else next.delete(name)
  picked.value = next
}

function show() {
  picked.value = new Set(props.allowedTools)
  modal.value.show()
}

function done() {
  if (!props.editable) return
  emit(
    'save',
    props.availableTools
      .map((tool) => tool.name)
      .filter((name) => picked.value.has(name))
  )
  modal.value.hide()
}

defineExpose({ show })
</script>
