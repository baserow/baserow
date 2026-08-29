<template>
  <Modal ref="modal" @show="init()">
    <h2 class="box__title">{{ $t('agentWorkspaceTools.title') }}</h2>
    <p>{{ $t('agentWorkspaceTools.description') }}</p>
    <div v-if="loading" class="loading"></div>
    <template v-else>
      <div v-if="canUpdate" class="agent-workspace-tools-modal__presets">
        <Button type="secondary" size="small" @click="selectAll()">
          {{ $t('agentWorkspaceTools.selectAll') }}
        </Button>
        <Button type="secondary" size="small" @click="selectReadOnly()">
          {{ $t('agentWorkspaceTools.selectReadOnly') }}
        </Button>
      </div>
      <div class="agent-workspace-tools-modal__groups">
        <div
          v-for="group in groupedTools"
          :key="group.name"
          class="agent-workspace-tools-modal__group"
        >
          <div class="agent-workspace-tools-modal__group-title">
            {{ group.label }}
          </div>
          <div
            v-for="groupTool in group.tools"
            :key="groupTool.name"
            class="agent-workspace-tools-modal__tool"
          >
            <Checkbox
              :checked="isChecked(groupTool.name)"
              :disabled="!canUpdate"
              @input="toggleTool(groupTool.name, $event)"
              >{{ humanizeToolName(groupTool.name) }}</Checkbox
            >
            <span
              class="agent-workspace-tools-modal__badge"
              :class="{
                'agent-workspace-tools-modal__badge--write': groupTool.is_write,
              }"
              >{{
                groupTool.is_write
                  ? $t('agentWorkspaceTools.write')
                  : $t('agentWorkspaceTools.read')
              }}</span
            >
          </div>
        </div>
      </div>
      <div class="actions actions--right actions--gap margin-bottom-0">
        <Button type="secondary" size="large" @click="hide()">
          {{ $t('action.cancel') }}
        </Button>
        <Button v-if="canUpdate" size="large" :loading="saving" @click="save()">
          {{ $t('action.save') }}
        </Button>
      </div>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import { notifyIf } from '@baserow/modules/core/utils/error'
import AgentApplicationService from '@baserow_enterprise/services/agentApplication'
import {
  getInitialWorkspaceToolSelection,
  buildWorkspaceToolsSavePayload,
} from '@baserow_enterprise/utils/agentWorkspaceTools'

// Groups in the order they should be listed; unknown groups returned by a
// newer backend are appended after these with a humanized fallback label.
const GROUP_ORDER = [
  'core',
  'database',
  'automation',
  'builder',
  'search_user_docs',
]

export default {
  name: 'AgentWorkspaceToolsModal',
  mixins: [modal],
  props: {
    application: {
      type: Object,
      required: true,
    },
    tool: {
      type: Object,
      required: true,
    },
    canUpdate: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['saved'],
  data() {
    return {
      loading: false,
      saving: false,
      tools: [],
      selected: [],
    }
  },
  computed: {
    groupedTools() {
      const groups = new Map()
      this.tools.forEach((tool) => {
        if (!groups.has(tool.group)) {
          groups.set(tool.group, {
            name: tool.group,
            label: this.groupLabel(tool.group),
            tools: [],
          })
        }
        groups.get(tool.group).tools.push(tool)
      })
      return [...groups.values()].sort((a, b) => {
        const indexA = GROUP_ORDER.indexOf(a.name)
        const indexB = GROUP_ORDER.indexOf(b.name)
        return (
          (indexA === -1 ? GROUP_ORDER.length : indexA) -
          (indexB === -1 ? GROUP_ORDER.length : indexB)
        )
      })
    },
  },
  methods: {
    async init() {
      this.loading = true
      try {
        const { data } = await AgentApplicationService(
          this.$client
        ).getWorkspaceTools(this.application.id)
        this.tools = data
        this.selected = getInitialWorkspaceToolSelection(this.tool.config, data)
      } catch (error) {
        this.hide()
        notifyIf(error, 'application')
      } finally {
        this.loading = false
      }
    },
    groupLabel(group) {
      if (GROUP_ORDER.includes(group)) {
        return this.$t(`agentWorkspaceTools.group_${group}`)
      }
      return this.humanizeToolName(group)
    },
    humanizeToolName(name) {
      return name.replaceAll('_', ' ')
    },
    isChecked(name) {
      return this.selected.includes(name)
    },
    toggleTool(name, checked) {
      if (checked) {
        if (!this.isChecked(name)) {
          this.selected.push(name)
        }
      } else {
        this.selected = this.selected.filter((selected) => selected !== name)
      }
    },
    selectAll() {
      this.selected = this.tools.map((tool) => tool.name)
    },
    selectReadOnly() {
      this.selected = this.tools
        .filter((tool) => !tool.is_write)
        .map((tool) => tool.name)
    },
    async save() {
      this.saving = true
      const payload = buildWorkspaceToolsSavePayload(this.selected, this.tools)
      try {
        await this.$store.dispatch('agentApplication/updateTool', {
          toolId: this.tool.id,
          values: { config: { ...(this.tool.config || {}), ...payload } },
        })
        // Lets the section show "x of y tools enabled" without refetching.
        this.$emit('saved', this.tools.length)
        this.hide()
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.saving = false
      }
    },
  },
}
</script>
