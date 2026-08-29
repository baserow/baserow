<template>
  <div>
    <div
      v-for="builtIn in builtInTools"
      :key="builtIn.type"
      class="agent-configuration__tool margin-bottom-2"
    >
      <SwitchInput
        small
        :value="builtInToolValue(builtIn.type)"
        :disabled="!canToggleTools"
        @input="toggleBuiltInTool(builtIn.type, $event)"
        >{{ builtIn.label }}</SwitchInput
      >
      <div class="agent-configuration__tool-helper">
        {{ builtIn.helper }}
      </div>
      <div
        v-if="builtIn.type === 'workspace' && !application.agent_identity_id"
        class="agent-configuration__tool-warning"
      >
        <i class="iconoir-warning-circle"></i>
        {{ $t('agentTools.workspaceIdentityWarning') }}
      </div>
      <div
        v-if="builtIn.type === 'workspace' && workspaceTool"
        class="agent-configuration__tool-options"
      >
        <RadioGroup
          :model-value="workspaceMode"
          :options="workspaceModeOptions"
          type="button"
          @input="onWorkspaceModeChange"
        ></RadioGroup>
        <div class="agent-configuration__tool-summary">
          {{ workspaceToolsSummary }}
          <template v-if="canUpdateTool">
            ·
            <a
              class="agent-configuration__tool-summary-link"
              @click="$refs.workspaceToolsModal.show()"
              >{{ $t('agentTools.chooseTools') }}</a
            >
          </template>
        </div>
        <div v-if="workspaceMode === 'read_write'">
          <SwitchInput
            small
            :value="workspaceRequireWriteApproval"
            :disabled="!canUpdateTool"
            @input="onWorkspaceWriteApprovalChange"
            >{{ $t('agentTools.requireWriteApproval') }}</SwitchInput
          >
          <div class="agent-configuration__tool-helper">
            {{ $t('agentTools.requireWriteApprovalHelper') }}
          </div>
        </div>
      </div>
    </div>
    <div class="agent-configuration__subsection-title">
      {{ $t('agentTools.actionTools') }}
    </div>
    <div
      v-if="actionTools.length === 0"
      class="agent-configuration__placeholder"
      :class="{ 'margin-bottom-2': canCreateTool }"
    >
      {{ $t('agentTools.noActionTools') }}
    </div>
    <div v-else class="agent-configuration__card-list">
      <div
        v-for="tool in actionTools"
        :key="tool.id"
        class="agent-configuration__card"
      >
        <div class="agent-configuration__card-header">
          <a
            class="agent-configuration__card-summary"
            @click="toggleExpanded(tool)"
          >
            <i
              class="agent-configuration__card-chevron iconoir-nav-arrow-right"
              :class="{
                'agent-configuration__card-chevron--expanded': isExpanded(
                  tool.id
                ),
              }"
            ></i>
            <i
              class="agent-configuration__card-icon"
              :class="serviceTypeIcon(tool)"
            ></i>
            <div class="agent-configuration__card-name">
              {{ toolTitle(tool) }}
            </div>
          </a>
          <ButtonIcon
            v-if="canDeleteTool"
            icon="iconoir-bin"
            :title="$t('agentTools.deleteTool')"
            @click="deleteTool(tool)"
          ></ButtonIcon>
        </div>
        <div
          v-if="isExpanded(tool.id) && toolDrafts[tool.id]"
          class="agent-configuration__card-body"
        >
          <ReadOnlyForm :read-only="!canUpdateTool">
            <FormGroup
              small-label
              :label="$t('agentTools.nameLabel')"
              :helper-text="
                tool.type === 'mcp' ? $t('agentTools.mcpNameHelper') : null
              "
              class="margin-bottom-2"
            >
              <FormInput
                v-model="toolDrafts[tool.id].name"
                :disabled="!canUpdateTool"
                :placeholder="
                  tool.type === 'mcp'
                    ? $t('agentTools.mcpNamePlaceholder')
                    : $t('agentTools.namePlaceholder')
                "
                @input="onNameChanged(tool)"
              ></FormInput>
            </FormGroup>
            <template v-if="tool.type === 'mcp'">
              <FormGroup
                small-label
                :label="$t('agentTools.mcpUrlLabel')"
                class="margin-bottom-2"
              >
                <FormInput
                  v-model="toolDrafts[tool.id].url"
                  :disabled="!canUpdateTool"
                  :placeholder="$t('agentTools.mcpUrlPlaceholder')"
                  @input="onConfigChanged(tool)"
                ></FormInput>
              </FormGroup>
              <FormGroup
                small-label
                :label="$t('agentTools.mcpHeadersLabel')"
                :helper-text="$t('agentTools.mcpHeadersHelper')"
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
                    :placeholder="$t('agentTools.mcpHeaderNamePlaceholder')"
                    @input="onConfigChanged(tool)"
                  ></FormInput>
                  <FormInput
                    v-model="header.value"
                    class="agent-configuration__key-value-value"
                    :disabled="!canUpdateTool"
                    :placeholder="$t('agentTools.mcpHeaderValuePlaceholder')"
                    @input="onConfigChanged(tool)"
                  ></FormInput>
                  <ButtonIcon
                    v-if="canUpdateTool"
                    icon="iconoir-bin"
                    :title="$t('agentTools.removeHeader')"
                    @click="removeHeader(tool, index)"
                  ></ButtonIcon>
                </div>
                <ButtonText
                  v-if="canUpdateTool"
                  icon="iconoir-plus"
                  @click="addHeader(tool)"
                >
                  {{ $t('agentTools.addHeader') }}
                </ButtonText>
              </FormGroup>
            </template>
            <template v-else>
              <FormGroup
                small-label
                :label="$t('agentTools.descriptionLabel')"
                :helper-text="$t('agentTools.descriptionHelper')"
                class="margin-bottom-2"
              >
                <FormTextarea
                  v-model="toolDrafts[tool.id].description"
                  :rows="3"
                  :disabled="!canUpdateTool"
                  :placeholder="$t('agentTools.descriptionPlaceholder')"
                  @input="onConfigChanged(tool)"
                ></FormTextarea>
              </FormGroup>
              <FormGroup
                small-label
                :label="$t('agentTools.inputsLabel')"
                :helper-text="$t('agentTools.inputsHelper')"
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
                    :placeholder="$t('agentTools.inputNamePlaceholder')"
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
                      :name="$t(`agentTools.inputType_${inputType}`)"
                      :value="inputType"
                    />
                  </Dropdown>
                  <FormInput
                    v-model="input.description"
                    class="agent-configuration__tool-input-description"
                    :disabled="!canUpdateTool"
                    :placeholder="$t('agentTools.inputDescriptionPlaceholder')"
                    @input="onConfigChanged(tool)"
                  ></FormInput>
                  <Checkbox
                    v-model="input.required"
                    :disabled="!canUpdateTool"
                    @input="onConfigChanged(tool)"
                    >{{ $t('agentTools.inputRequired') }}</Checkbox
                  >
                  <ButtonIcon
                    v-if="canUpdateTool"
                    icon="iconoir-bin"
                    :title="$t('agentTools.removeInput')"
                    @click="removeInput(tool, index)"
                  ></ButtonIcon>
                </div>
                <ButtonText
                  v-if="canUpdateTool"
                  icon="iconoir-plus"
                  @click="addInput(tool)"
                >
                  {{ $t('agentTools.addInput') }}
                </ButtonText>
              </FormGroup>
            </template>
            <div class="margin-bottom-2">
              <SwitchInput
                small
                :value="toolDrafts[tool.id].requireApproval"
                :disabled="!canUpdateTool"
                @input="onRequireApprovalChanged(tool, $event)"
                >{{ $t('agentTools.requireApproval') }}</SwitchInput
              >
              <div class="agent-configuration__tool-helper">
                {{ $t('agentTools.requireApprovalHelper') }}
              </div>
            </div>
            <AgentServiceForm
              v-if="serviceType(tool)"
              :key="`${tool.id}-${tool.service_type}`"
              :application="application"
              :service-type="serviceType(tool)"
              :service="tool.service || {}"
              :tool="tool"
              @values-changed="onServiceValuesChanged(tool, $event)"
            />
          </ReadOnlyForm>
        </div>
      </div>
    </div>
    <template v-if="canCreateTool">
      <Button
        type="secondary"
        icon="iconoir-plus"
        :loading="addLoading"
        @click="
          $refs.addToolContext.toggle($event.currentTarget, 'bottom', 'left', 4)
        "
      >
        {{ $t('agentTools.addActionTool') }}
      </Button>
      <Context
        ref="addToolContext"
        max-height-if-outside-viewport
        @shown="$refs.addToolMenu.focus()"
      >
        <AgentGroupedAddMenu
          ref="addToolMenu"
          :items="toolMenuItems"
          :search-placeholder="$t('agentTools.searchPlaceholder')"
          :empty-text="$t('agentTools.noResults')"
          @select="onAddToolSelect($event)"
          @close="$refs.addToolContext.hide()"
        />
      </Context>
    </template>
    <!--
      Outside the built-in tools v-for on purpose: a string ref inside a
      v-for collects into an array, which breaks `$refs...show()`.
    -->
    <AgentWorkspaceToolsModal
      v-if="workspaceTool"
      ref="workspaceToolsModal"
      :application="application"
      :tool="workspaceTool"
      :can-update="canUpdateTool"
      @saved="workspaceToolsTotal = $event"
    />
  </div>
</template>

<script>
import debounce from 'lodash/debounce'
import isEqual from 'lodash/isEqual'
import ReadOnlyForm from '@baserow/modules/core/components/ReadOnlyForm'
import AgentServiceForm from '@baserow_enterprise/components/agentApplication/AgentServiceForm'
import AgentGroupedAddMenu from '@baserow_enterprise/components/agentApplication/AgentGroupedAddMenu'
import AgentWorkspaceToolsModal from '@baserow_enterprise/components/agentApplication/AgentWorkspaceToolsModal'
import AgentApplicationService from '@baserow_enterprise/services/agentApplication'
import { notifyIf } from '@baserow/modules/core/utils/error'

const BUILT_IN_TOOL_TYPES = ['workspace', 'workspace_search', 'web_search']

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
  name: 'AgentToolsSection',
  components: {
    AgentGroupedAddMenu,
    AgentServiceForm,
    AgentWorkspaceToolsModal,
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
      // Desired state per built-in tool type while its create/delete request
      // is being synced; the switch shows this intent instead of the store
      // state so toggling is optimistic and never blocks.
      pendingBuiltIn: {},
      addLoading: false,
      // Newly added tools start expanded; existing ones start collapsed so
      // that multiple tools stay scannable.
      expandedToolIds: [],
      // Local editable copies of the name/config fields per tool id, so a
      // save response can never clobber what the user is still typing.
      toolDrafts: {},
      // Unsaved values per tool id, flushed by a per-tool debounced save.
      pendingToolValues: {},
      inputTypes: INPUT_TYPES,
      // Total number of available workspace tools, fetched lazily because the
      // summary only needs it when a custom selection is active.
      workspaceToolsTotal: null,
      workspaceToolsTotalLoading: false,
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
    canToggleTools() {
      // Toggling a built-in tool either creates or deletes its row.
      return this.canCreateTool && this.canDeleteTool
    },
    tools() {
      return this.$store.getters['agentApplication/getTools']
    },
    actionTools() {
      return this.tools.filter((tool) => ['service', 'mcp'].includes(tool.type))
    },
    workspaceTool() {
      return this.tools.find((tool) => tool.type === 'workspace') || null
    },
    workspaceMode() {
      return this.workspaceTool?.config?.mode === 'read_only'
        ? 'read_only'
        : 'read_write'
    },
    workspaceModeOptions() {
      return [
        {
          value: 'read_write',
          label: this.$t('agentTools.workspaceModeReadWrite'),
          disabled: !this.canUpdateTool,
        },
        {
          value: 'read_only',
          label: this.$t('agentTools.workspaceModeReadOnly'),
          disabled: !this.canUpdateTool,
        },
      ]
    },
    workspaceRequireWriteApproval() {
      return this.workspaceTool?.config?.require_write_approval !== false
    },
    workspaceEnabledTools() {
      return this.workspaceTool?.config?.enabled_tools ?? null
    },
    workspaceToolsSummary() {
      const enabledTools = this.workspaceEnabledTools
      if (Array.isArray(enabledTools)) {
        if (this.workspaceToolsTotal !== null) {
          return this.$t('agentTools.countOfTotalToolsEnabled', {
            count: enabledTools.length,
            total: this.workspaceToolsTotal,
          })
        }
        return this.$t('agentTools.countToolsEnabled', {
          count: enabledTools.length,
        })
      }
      return this.workspaceMode === 'read_only'
        ? this.$t('agentTools.allReadToolsEnabled')
        : this.$t('agentTools.allToolsEnabled')
    },
    builtInTools() {
      return BUILT_IN_TOOL_TYPES.map((type) => ({
        type,
        label: this.$t(`agentTools.${type}Label`),
        helper: this.$t(`agentTools.${type}Helper`),
      }))
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
        label: this.$t('agentTools.externalToolsGroup'),
        icon: 'iconoir-globe',
        iconColor: 'muted-blue',
        children: [
          {
            id: 'tool-mcp',
            label: this.$t('agentTools.mcpServer'),
            value: 'mcp',
            icon: 'iconoir-globe',
            iconColor: 'muted-blue',
            description: this.$t('agentTools.mcpServerDescription'),
          },
        ],
      })
      return items
    },
  },
  watch: {
    workspaceEnabledTools: {
      immediate: true,
      handler(enabledTools) {
        if (Array.isArray(enabledTools)) {
          this.fetchWorkspaceToolsTotal()
        }
      },
    },
  },
  created() {
    this.debouncedToolSaves = {}
  },
  beforeUnmount() {
    Object.values(this.debouncedToolSaves).forEach((save) => save.flush())
  },
  // The tools are fetched by the page, so the unconfigured-agent heuristic
  // can be evaluated before the panel is opened.
  methods: {
    hasBuiltInTool(type) {
      return this.tools.some((tool) => tool.type === type)
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
        return this.$t('agentTools.mcpServer')
      }
      return this.serviceType(tool)?.name || tool.service_type
    },
    toolTitle(tool) {
      const draftName = this.toolDrafts[tool.id]?.name
      return (draftName ?? tool.name) || this.serviceTypeName(tool)
    },
    isExpanded(toolId) {
      return this.expandedToolIds.includes(toolId)
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
    toggleExpanded(tool) {
      if (this.isExpanded(tool.id)) {
        this.expandedToolIds = this.expandedToolIds.filter(
          (id) => id !== tool.id
        )
      } else {
        this.ensureDraft(tool)
        this.expandedToolIds.push(tool.id)
      }
    },
    builtInToolValue(type) {
      return type in this.pendingBuiltIn
        ? this.pendingBuiltIn[type]
        : this.hasBuiltInTool(type)
    },
    async toggleBuiltInTool(type, enabled) {
      const syncing = type in this.pendingBuiltIn
      this.pendingBuiltIn[type] = enabled
      if (syncing) {
        // The running sync loop below picks up the latest intent.
        return
      }
      try {
        // Sync until the store matches the latest intent, so rapid toggling
        // serializes into follow-up requests instead of racing a create
        // against a delete.
        while (this.pendingBuiltIn[type] !== this.hasBuiltInTool(type)) {
          if (this.pendingBuiltIn[type]) {
            await this.$store.dispatch('agentApplication/createTool', {
              applicationId: this.application.id,
              values: { type },
            })
          } else {
            const tool = this.tools.find((t) => t.type === type)
            if (!tool) {
              break
            }
            await this.$store.dispatch('agentApplication/deleteTool', {
              toolId: tool.id,
            })
          }
        }
      } catch (error) {
        // Dropping the pending intent reverts the switch to the store state.
        notifyIf(error, 'application')
      } finally {
        delete this.pendingBuiltIn[type]
      }
    },
    async saveWorkspaceConfig(values) {
      const tool = this.workspaceTool
      if (!tool || !this.canUpdateTool) {
        return
      }
      try {
        await this.$store.dispatch('agentApplication/updateTool', {
          toolId: tool.id,
          values: { config: { ...(tool.config || {}), ...values } },
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
    async fetchWorkspaceToolsTotal() {
      if (
        this.workspaceToolsTotal !== null ||
        this.workspaceToolsTotalLoading
      ) {
        return
      }
      this.workspaceToolsTotalLoading = true
      try {
        const { data } = await AgentApplicationService(
          this.$client
        ).getWorkspaceTools(this.application.id)
        this.workspaceToolsTotal = data.length
      } catch {
        // The summary falls back to a count without a total.
      } finally {
        this.workspaceToolsTotalLoading = false
      }
    },
    onWorkspaceModeChange(mode) {
      const values = { mode }
      if (Array.isArray(this.workspaceEnabledTools)) {
        // The mode presets always mean "all (read) tools", so they reset any
        // custom selection made in the choose tools modal.
        values.enabled_tools = null
      } else if (mode === this.workspaceMode) {
        return
      }
      this.saveWorkspaceConfig(values)
    },
    onWorkspaceWriteApprovalChange(enabled) {
      this.saveWorkspaceConfig({ require_write_approval: enabled })
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
        this.expandedToolIds.push(tool.id)
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
        this.expandedToolIds.push(tool.id)
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.addLoading = false
      }
    },
    async deleteTool(tool) {
      delete this.pendingToolValues[tool.id]
      delete this.debouncedToolSaves[tool.id]
      delete this.toolDrafts[tool.id]
      try {
        await this.$store.dispatch('agentApplication/deleteTool', {
          toolId: tool.id,
        })
      } catch (error) {
        notifyIf(error, 'application')
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
