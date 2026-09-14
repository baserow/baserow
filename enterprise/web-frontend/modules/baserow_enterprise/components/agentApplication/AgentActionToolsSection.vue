<template>
  <div>
    <div class="agent-configuration__subsection">
      <div class="agent-configuration__subsection-title">
        {{ $t('agentActionTools.actions') }}
      </div>
      <ButtonText
        v-if="canCreateTool"
        icon="iconoir-plus"
        :loading="addLoading"
        @click="
          $refs.addToolContext.toggle(
            $event.currentTarget,
            'bottom',
            'right',
            4
          )
        "
      >
        {{ $t('agentActionTools.addAction') }}
      </ButtonText>
    </div>
    <div class="agent-configuration__intro">
      {{ $t('agentActionTools.intro') }}
    </div>
    <div
      v-if="actionTools.length === 0"
      class="agent-configuration__placeholder"
    >
      {{ $t('agentActionTools.empty') }}
    </div>
    <div v-else class="agent-configuration__card-list">
      <AgentConfigurationCard
        v-for="tool in actionTools"
        :key="tool.id"
        :title="serviceTypeName(tool)"
        :subtitle="cardSubtitle(tool)"
        :icon="serviceTypeIcon(tool)"
      >
        <template v-if="toolDrafts[tool.id]">
          <ReadOnlyForm :read-only="!canUpdateTool">
            <FormGroup
              small-label
              :label="$t('agentActionTools.nameLabel')"
              :helper-text="
                tool.type === 'mcp'
                  ? $t('agentActionTools.mcpNameHelper')
                  : null
              "
              class="margin-bottom-2"
            >
              <FormInput
                v-model="toolDrafts[tool.id].name"
                :disabled="!canUpdateTool"
                :placeholder="
                  tool.type === 'mcp'
                    ? $t('agentActionTools.mcpNamePlaceholder')
                    : $t('agentActionTools.namePlaceholder')
                "
                @input="onNameChanged(tool)"
              ></FormInput>
            </FormGroup>
            <template v-if="tool.type === 'mcp'">
              <FormGroup
                small-label
                :label="$t('agentActionTools.mcpUrlLabel')"
                class="margin-bottom-2"
              >
                <FormInput
                  v-model="toolDrafts[tool.id].url"
                  :disabled="!canUpdateTool"
                  :placeholder="$t('agentActionTools.mcpUrlPlaceholder')"
                  @input="onConfigChanged(tool)"
                ></FormInput>
              </FormGroup>
              <FormGroup
                small-label
                :label="$t('agentActionTools.mcpHeadersLabel')"
                :helper-text="$t('agentActionTools.mcpHeadersHelper')"
                class="margin-bottom-2"
              >
                <div
                  v-for="(header, index) in toolDrafts[tool.id].headers"
                  :key="index"
                  class="agent-configuration__key-value-row"
                >
                  <FormInput
                    v-model="header.name"
                    class="agent-configuration__key-value-name"
                    :disabled="!canUpdateTool"
                    :placeholder="
                      $t('agentActionTools.mcpHeaderNamePlaceholder')
                    "
                    @input="onConfigChanged(tool)"
                  ></FormInput>
                  <FormInput
                    v-model="header.value"
                    class="agent-configuration__key-value-value"
                    :disabled="!canUpdateTool"
                    :placeholder="
                      $t('agentActionTools.mcpHeaderValuePlaceholder')
                    "
                    @input="onConfigChanged(tool)"
                  ></FormInput>
                  <ButtonIcon
                    v-if="canUpdateTool"
                    icon="iconoir-bin"
                    :title="$t('agentActionTools.removeHeader')"
                    @click="removeHeader(tool, index)"
                  ></ButtonIcon>
                </div>
                <ButtonText
                  v-if="canUpdateTool"
                  icon="iconoir-plus"
                  @click="addHeader(tool)"
                >
                  {{ $t('agentActionTools.addHeader') }}
                </ButtonText>
              </FormGroup>
            </template>
            <template v-else>
              <FormGroup
                small-label
                :label="$t('agentActionTools.descriptionLabel')"
                :helper-text="$t('agentActionTools.descriptionHelper')"
                class="margin-bottom-2"
              >
                <FormTextarea
                  v-model="toolDrafts[tool.id].description"
                  :rows="3"
                  :disabled="!canUpdateTool"
                  :placeholder="$t('agentActionTools.descriptionPlaceholder')"
                  @input="onConfigChanged(tool)"
                ></FormTextarea>
              </FormGroup>
              <FormGroup
                small-label
                :label="$t('agentActionTools.inputsLabel')"
                :helper-text="$t('agentActionTools.inputsHelper')"
                class="margin-bottom-2"
              >
                <div
                  v-for="(input, index) in toolDrafts[tool.id].inputs"
                  :key="index"
                  class="agent-configuration__tool-input-row"
                >
                  <FormInput
                    v-model="input.name"
                    class="agent-configuration__tool-input-name"
                    :disabled="!canUpdateTool"
                    :placeholder="$t('agentActionTools.inputNamePlaceholder')"
                    @input="onConfigChanged(tool)"
                  ></FormInput>
                  <Dropdown
                    v-model="input.type"
                    :show-search="false"
                    :fixed-items="true"
                    :disabled="!canUpdateTool"
                    @change="onConfigChanged(tool)"
                  >
                    <DropdownItem
                      v-for="inputType in inputTypes"
                      :key="inputType"
                      :name="$t(`agentActionTools.inputType_${inputType}`)"
                      :value="inputType"
                    />
                  </Dropdown>
                  <FormInput
                    v-model="input.description"
                    class="agent-configuration__tool-input-description"
                    :disabled="!canUpdateTool"
                    :placeholder="
                      $t('agentActionTools.inputDescriptionPlaceholder')
                    "
                    @input="onConfigChanged(tool)"
                  ></FormInput>
                  <Checkbox
                    v-model="input.required"
                    :disabled="!canUpdateTool"
                    @input="onConfigChanged(tool)"
                    >{{ $t('agentActionTools.inputRequired') }}</Checkbox
                  >
                  <ButtonIcon
                    v-if="canUpdateTool"
                    icon="iconoir-bin"
                    :title="$t('agentActionTools.removeInput')"
                    @click="removeInput(tool, index)"
                  ></ButtonIcon>
                </div>
                <ButtonText
                  v-if="canUpdateTool"
                  icon="iconoir-plus"
                  @click="addInput(tool)"
                >
                  {{ $t('agentActionTools.addInput') }}
                </ButtonText>
              </FormGroup>
            </template>
            <FormGroup
              small-label
              :label="$t('agentActionTools.beforeRunning')"
              class="margin-bottom-2"
            >
              <SegmentControl
                :segments="beforeRunningSegments"
                :active-index="toolDrafts[tool.id].requireApproval ? 0 : 1"
                @update:active-index="
                  onRequireApprovalChanged(tool, $event === 0)
                "
              ></SegmentControl>
            </FormGroup>
            <Expandable v-if="serviceType(tool)" class="margin-bottom-2">
              <template #header="{ toggle, expanded }">
                <a
                  class="agent-configuration__expand-link"
                  @click.prevent="toggle"
                >
                  <i
                    class="agent-configuration__card-chevron iconoir-nav-arrow-right"
                    :class="{
                      'agent-configuration__card-chevron--expanded': expanded,
                    }"
                  ></i>
                  {{ $t('agentActionTools.configure') }}
                </a>
              </template>
              <div class="agent-configuration__expand-body">
                <AgentServiceForm
                  :key="`${tool.id}-${tool.service_type}`"
                  :application="application"
                  :service-type="serviceType(tool)"
                  :service="tool.service || {}"
                  :tool="tool"
                  @values-changed="onServiceValuesChanged(tool, $event)"
                />
              </div>
            </Expandable>
          </ReadOnlyForm>
        </template>
        <template v-if="canDeleteTool" #footer>
          <ButtonText
            icon="iconoir-bin"
            :loading="deletingIds.includes(tool.id)"
            @click="deleteTool(tool)"
          >
            {{
              tool.type === 'mcp'
                ? $t('agentActionTools.deleteServer')
                : $t('agentActionTools.delete')
            }}
          </ButtonText>
        </template>
      </AgentConfigurationCard>
    </div>
    <template v-if="canCreateTool">
      <Context
        ref="addToolContext"
        max-height-if-outside-viewport
        @shown="$refs.addToolMenu.focus()"
      >
        <AgentGroupedAddMenu
          ref="addToolMenu"
          :items="toolMenuItems"
          :search-placeholder="$t('agentActionTools.searchPlaceholder')"
          :empty-text="$t('agentActionTools.noResults')"
          @select="onAddToolSelect($event)"
          @close="$refs.addToolContext.hide()"
        />
      </Context>
    </template>
  </div>
</template>

<script>
import debounce from 'lodash/debounce'
import isEqual from 'lodash/isEqual'
import ReadOnlyForm from '@baserow/modules/core/components/ReadOnlyForm'
import AgentServiceForm from '@baserow_enterprise/components/agentApplication/AgentServiceForm'
import AgentGroupedAddMenu from '@baserow_enterprise/components/agentApplication/AgentGroupedAddMenu'
import AgentConfigurationCard from '@baserow_enterprise/components/agentApplication/AgentConfigurationCard'
import { notifyIf } from '@baserow/modules/core/utils/error'

/**
 * Only the workflow action services whose configuration forms work outside the
 * automation editor (no router edges, goto destinations or preceding node data
 * providers) can be offered as agent action tools. Note that these must be
 * service type names, not automation node type names; the upsert row service
 * covers both creating and updating rows.
 */
const SUPPORTED_SERVICE_TYPES = [
  'local_baserow_upsert_row',
  'local_baserow_delete_row',
  'http_request',
  'smtp_email',
]

const INPUT_TYPES = ['string', 'number', 'boolean']

export default {
  name: 'AgentActionToolsSection',
  components: {
    AgentConfigurationCard,
    AgentGroupedAddMenu,
    AgentServiceForm,
    ReadOnlyForm,
  },
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      addLoading: false,
      deletingIds: [],
      // Local editable copies of the name/config fields per tool id, so a
      // save response can never clobber what the user is still typing.
      toolDrafts: {},
      // Unsaved values per tool id, flushed by a per-tool debounced save.
      pendingToolValues: {},
      inputTypes: INPUT_TYPES,
    }
  },
  computed: {
    canCreateTool() {
      return this.$hasPermission(
        'agent_application.create_tool',
        this.application,
        this.application.workspace.id
      )
    },
    canUpdateTool() {
      return this.$hasPermission(
        'agent_application.update_tool',
        this.application,
        this.application.workspace.id
      )
    },
    canDeleteTool() {
      return this.$hasPermission(
        'agent_application.delete_tool',
        this.application,
        this.application.workspace.id
      )
    },
    tools() {
      return this.$store.getters['agentApplication/getTools']
    },
    actionTools() {
      return this.tools.filter((tool) => ['service', 'mcp'].includes(tool.type))
    },
    beforeRunningSegments() {
      return [
        { label: this.$t('agentActionTools.askMe') },
        { label: this.$t('agentActionTools.justRun') },
      ]
    },
    availableServiceTypes() {
      return SUPPORTED_SERVICE_TYPES.map((type) => {
        try {
          return this.$registry.get('service', type)
        } catch {
          return null
        }
      }).filter(
        (serviceType) => serviceType !== null && serviceType.isWorkflowAction
      )
    },
    toolMenuItems() {
      const groups = new Map()
      this.availableServiceTypes.forEach((serviceType) => {
        const group = serviceType.group
        if (!groups.has(group.id)) {
          groups.set(group.id, { ...group, children: [] })
        }
        groups.get(group.id).children.push({
          id: `tool-${serviceType.getType()}`,
          label: serviceType.name,
          value: serviceType.getType(),
          icon: serviceType.icon,
          iconColor: serviceType.iconColor,
          description: serviceType.description,
          meta: serviceType,
        })
      })
      const items = Array.from(groups.values())
      items.push({
        id: 'external-tools',
        label: this.$t('agentActionTools.externalToolsGroup'),
        icon: 'iconoir-globe',
        iconColor: 'muted-blue',
        children: [
          {
            id: 'tool-mcp',
            label: this.$t('agentActionTools.mcpServer'),
            value: 'mcp',
            icon: 'iconoir-globe',
            iconColor: 'muted-blue',
            description: this.$t('agentActionTools.mcpServerDescription'),
          },
        ],
      })
      return items
    },
  },
  created() {
    this.debouncedToolSaves = {}
  },
  mounted() {
    this.actionTools.forEach((tool) => this.ensureDraft(tool))
  },
  watch: {
    actionTools(tools) {
      tools.forEach((tool) => this.ensureDraft(tool))
    },
  },
  beforeUnmount() {
    Object.values(this.debouncedToolSaves).forEach((save) => save.flush())
  },
  methods: {
    cardSubtitle(tool) {
      // The tool name only adds information when it differs from the type.
      const name = this.toolDrafts[tool.id]?.name
      return name && name !== this.serviceTypeName(tool) ? name : ''
    },
    serviceType(tool) {
      try {
        return this.$registry.get('service', tool.service_type)
      } catch {
        return null
      }
    },
    serviceTypeIcon(tool) {
      if (tool.type === 'mcp') {
        return 'iconoir-globe'
      }
      return this.serviceType(tool)?.icon || 'iconoir-tools'
    },
    serviceTypeName(tool) {
      if (tool.type === 'mcp') {
        return this.$t('agentActionTools.mcpServer')
      }
      return this.serviceType(tool)?.name || tool.service_type
    },
    ensureDraft(tool) {
      if (this.toolDrafts[tool.id]) {
        return
      }
      if (tool.type === 'mcp') {
        this.toolDrafts[tool.id] = {
          name: tool.name || '',
          url: tool.config?.url || '',
          headers: Object.entries(tool.config?.headers || {}).map(
            ([name, value]) => ({ name, value })
          ),
          requireApproval: tool.config?.require_approval !== false,
        }
      } else {
        this.toolDrafts[tool.id] = {
          name: tool.name || '',
          description: tool.config?.description || '',
          inputs: (tool.config?.inputs || []).map((input) => ({ ...input })),
          requireApproval: tool.config?.require_approval !== false,
        }
      }
    },
    onAddToolSelect(item) {
      if (item.value === 'mcp') {
        this.addMcpTool()
      } else {
        this.addActionTool(item.meta)
      }
    },
    async addMcpTool() {
      this.$refs.addToolContext.hide()
      this.addLoading = true
      try {
        const tool = await this.$store.dispatch('agentApplication/createTool', {
          applicationId: this.application.id,
          values: {
            type: 'mcp',
            name: '',
            config: { url: '', headers: {}, require_approval: true },
          },
        })
        this.ensureDraft(tool)
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.addLoading = false
      }
    },
    async addActionTool(serviceType) {
      this.$refs.addToolContext.hide()
      this.addLoading = true
      try {
        const tool = await this.$store.dispatch('agentApplication/createTool', {
          applicationId: this.application.id,
          values: {
            type: 'service',
            name: serviceType.name,
            config: {},
            service_type: serviceType.getType(),
            service: {},
          },
        })
        this.ensureDraft(tool)
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.addLoading = false
      }
    },
    async deleteTool(tool) {
      if (this.deletingIds.includes(tool.id)) {
        return
      }
      delete this.pendingToolValues[tool.id]
      delete this.debouncedToolSaves[tool.id]
      this.deletingIds = [...this.deletingIds, tool.id]
      try {
        await this.$store.dispatch('agentApplication/deleteTool', {
          toolId: tool.id,
        })
        delete this.toolDrafts[tool.id]
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.deletingIds = this.deletingIds.filter((id) => id !== tool.id)
      }
    },
    addInput(tool) {
      // An input only reaches the saved config once it has a name, so adding
      // an empty row doesn't need to save anything.
      this.toolDrafts[tool.id].inputs.push({
        name: '',
        type: 'string',
        description: '',
        required: false,
      })
    },
    removeInput(tool, index) {
      this.toolDrafts[tool.id].inputs.splice(index, 1)
      this.onConfigChanged(tool)
    },
    addHeader(tool) {
      // A header only reaches the saved config once it has a name, so adding
      // an empty row doesn't need to save anything.
      this.toolDrafts[tool.id].headers.push({ name: '', value: '' })
    },
    removeHeader(tool, index) {
      this.toolDrafts[tool.id].headers.splice(index, 1)
      this.onConfigChanged(tool)
    },
    onRequireApprovalChanged(tool, enabled) {
      if (!this.canUpdateTool) {
        return
      }
      this.toolDrafts[tool.id].requireApproval = enabled
      this.queueSave(tool, { config: true })
    },
    // Name and config saves read the draft at save time instead of event
    // time, because the change event can fire before v-model has updated the
    // draft.
    onNameChanged(tool) {
      if (!this.canUpdateTool) {
        return
      }
      this.queueSave(tool, { name: true })
    },
    onConfigChanged(tool) {
      if (!this.canUpdateTool) {
        return
      }
      this.queueSave(tool, { config: true })
    },
    onServiceValuesChanged(tool, newValues) {
      if (!this.canUpdateTool) {
        return
      }
      const pending = this.pendingToolValues[tool.id]?.service || {}
      const current = {
        ...(tool.service || {}),
        ...pending,
      }
      const differences = Object.fromEntries(
        Object.entries(newValues).filter(
          ([key, value]) => !isEqual(value, current[key])
        )
      )
      if (Object.keys(differences).length === 0) {
        return
      }
      this.queueSave(tool, { service: { ...pending, ...differences } })
    },
    queueSave(tool, values) {
      this.pendingToolValues = {
        ...this.pendingToolValues,
        [tool.id]: { ...this.pendingToolValues[tool.id], ...values },
      }
      if (!this.debouncedToolSaves[tool.id]) {
        this.debouncedToolSaves[tool.id] = debounce(
          () => this.saveTool(tool.id),
          1000
        )
      }
      this.debouncedToolSaves[tool.id]()
    },
    async saveTool(toolId) {
      const tool = this.tools.find((t) => t.id === toolId)
      const pending = this.pendingToolValues[toolId]
      const draft = this.toolDrafts[toolId]
      if (!tool || !pending) {
        return
      }
      delete this.pendingToolValues[toolId]
      const values = {}
      if (pending.name && draft && draft.name !== tool.name) {
        values.name = draft.name
      }
      if (pending.config && draft) {
        const config =
          tool.type === 'mcp'
            ? {
                url: draft.url.trim(),
                headers: Object.fromEntries(
                  draft.headers
                    .filter((header) => header.name.trim() !== '')
                    .map((header) => [header.name.trim(), header.value])
                ),
                require_approval: draft.requireApproval,
              }
            : {
                description: draft.description,
                inputs: draft.inputs
                  .filter((input) => input.name.trim() !== '')
                  .map((input) => ({ ...input })),
                require_approval: draft.requireApproval,
              }
        if (!isEqual(config, tool.config || {})) {
          values.config = config
        }
      }
      if (pending.service && Object.keys(pending.service).length > 0) {
        values.service = { ...(tool.service || {}), ...pending.service }
      }
      if (Object.keys(values).length === 0) {
        return
      }
      try {
        await this.$store.dispatch('agentApplication/updateTool', {
          toolId,
          values,
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
  },
}
</script>
