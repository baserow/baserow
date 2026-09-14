<template>
  <div>
    <FormGroup
      small-label
      :label="$t('agentAccess.actsAs')"
      class="margin-bottom-1"
    >
      <Dropdown
        v-model="agentIdentity"
        :disabled="readOnly || saving"
        :show-search="false"
        :show-footer="canCreateIdentity"
      >
        <DropdownItem
          :name="$t('agentAccess.noneOption')"
          :value="null"
          icon="iconoir-prohibition"
        />
        <DropdownItem
          v-for="identity in identities"
          :key="identity.id"
          :name="identity.name"
          :value="identity.id"
          :description="roleName(identity)"
        >
          <span class="agent-configuration__identity-option">
            <Avatar
              :initials="identity.name.slice(0, 1).toUpperCase()"
              color="purple"
              size="small"
              rounded
            />
            <span class="agent-configuration__identity-name">{{
              identity.name
            }}</span>
            <Badge v-if="roleName(identity)" color="neutral" size="small">
              {{ roleName(identity) }}
            </Badge>
          </span>
        </DropdownItem>
        <template v-if="canCreateIdentity" #footer>
          <a
            class="select__footer-button"
            @click="$refs.manageAgentModal.show()"
          >
            <i class="iconoir-plus"></i>
            {{ $t('agentAccess.createIdentity') }}
          </a>
        </template>
      </Dropdown>
      <ManageAgentModal
        v-if="canCreateIdentity"
        ref="manageAgentModal"
        :workspace="workspace"
        :agent="null"
        @saved="onIdentityCreated"
      />
    </FormGroup>
    <div class="agent-configuration__hint margin-bottom-3">
      <template v-if="selectedIdentity">
        {{
          $t('agentAccess.actsAsHint', {
            role: roleName(selectedIdentity) || $t('agentAccess.member'),
            name: selectedIdentity.name,
          })
        }}
      </template>
      <template v-else>{{ $t('agentAccess.noIdentityHint') }}</template>
    </div>

    <div class="agent-configuration__switch-card">
      <div class="agent-configuration__switch-row">
        <i class="agent-configuration__switch-icon iconoir-tools"></i>
        <div class="agent-configuration__switch-text">
          <div class="agent-configuration__switch-title">
            {{ $t('agentAccess.workspaceTools') }}
          </div>
          <div class="agent-configuration__switch-description">
            {{ $t('agentAccess.workspaceToolsDescription') }}
          </div>
        </div>
        <SwitchInput
          small
          :value="builtInToolValue('workspace')"
          :disabled="!canToggleTools"
          @input="toggleBuiltInTool('workspace', $event)"
        ></SwitchInput>
      </div>
      <Alert
        v-if="builtInToolValue('workspace') && !application.agent_identity_id"
        type="warning"
        class="margin-top-2"
      >
        {{ $t('agentAccess.identityWarning') }}
      </Alert>
      <template v-if="workspaceTool">
        <SegmentControl
          class="agent-configuration__segment"
          :segments="accessSegments"
          :active-index="accessIndex"
          @update:active-index="onAccessChange"
        ></SegmentControl>
        <a
          v-if="config.access === 'custom'"
          class="agent-configuration__link"
          @click.prevent="openPermissions()"
        >
          {{ $t('agentAccess.editPermissions') }}
        </a>
        <div
          class="agent-configuration__switch-row agent-configuration__switch-row--nested"
          :class="{
            'agent-configuration__switch-row--disabled':
              config.access === 'read_only',
          }"
        >
          <div class="agent-configuration__switch-text">
            <div class="agent-configuration__switch-title">
              {{ $t('agentAccess.askBeforeChanges') }}
            </div>
            <div class="agent-configuration__switch-description">
              {{ $t('agentAccess.askBeforeChangesHint') }}
            </div>
          </div>
          <SwitchInput
            small
            :value="config.require_write_approval"
            :disabled="!canUpdateTool || config.access === 'read_only'"
            @input="onAskChange"
          ></SwitchInput>
        </div>
        <div
          v-if="groups.length > 0"
          class="agent-configuration__rows agent-configuration__rows--nested"
        >
          <AgentConfigurationSectionRow
            v-for="group in groups"
            :key="group.key"
            :icon="group.icon"
            :title="group.label"
            :right-label="group.presetLabel"
            @click="openPermissions(group.key)"
          />
        </div>
      </template>
    </div>

    <div
      v-for="builtIn in extraBuiltIns"
      :key="builtIn.type"
      class="agent-configuration__switch-row agent-configuration__switch-row--plain"
    >
      <i class="agent-configuration__switch-icon" :class="builtIn.icon"></i>
      <div class="agent-configuration__switch-text">
        <div class="agent-configuration__switch-title">{{ builtIn.label }}</div>
        <div class="agent-configuration__switch-description">
          {{ builtIn.description }}
        </div>
      </div>
      <SwitchInput
        small
        :value="builtInToolValue(builtIn.type)"
        :disabled="!canToggleTools"
        @input="toggleBuiltInTool(builtIn.type, $event)"
      ></SwitchInput>
    </div>

    <AgentToolPermissionsModal
      v-if="workspaceTool"
      ref="permissionsModal"
      :application="application"
      :tool="workspaceTool"
      :can-update="canUpdateTool"
    />
  </div>
</template>

<script>
import ManageAgentModal from '@baserow/modules/core/components/settings/agents/ManageAgentModal'
import { notifyIf } from '@baserow/modules/core/utils/error'
import AgentConfigurationSectionRow from '@baserow_enterprise/components/agentApplication/AgentConfigurationSectionRow'
import AgentToolPermissionsModal from '@baserow_enterprise/components/agentApplication/AgentToolPermissionsModal'
import {
  normalizeWorkspaceConfig,
  effectiveRules,
  deriveGroupPreset,
  ACCESS_EVERYTHING,
  ACCESS_READ_ONLY,
  ACCESS_CUSTOM,
  RULE_ALLOW,
  RULE_ASK,
  RULE_OFF,
} from '@baserow_enterprise/utils/agentToolPermissions'

const ACCESS_ORDER = [ACCESS_EVERYTHING, ACCESS_READ_ONLY, ACCESS_CUSTOM]
const GROUP_ICONS = {
  database: 'iconoir-db',
  automation: 'baserow-icon-automation',
  builder: 'iconoir-app-window',
  core: 'iconoir-settings',
  search_user_docs: 'iconoir-search',
}

export default {
  name: 'AgentAccessSection',
  components: {
    ManageAgentModal,
    AgentConfigurationSectionRow,
    AgentToolPermissionsModal,
  },
  props: {
    application: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      pendingIdentity: null,
      saving: false,
      // Desired state per built-in tool type while its create/delete request
      // is being synced; the switch shows this intent instead of the store
      // state so toggling is optimistic and never blocks.
      pendingBuiltIn: {},
    }
  },
  computed: {
    // The application's workspace object doesn't carry the roles needed by
    // the manage agent modal and the role badges, so the full workspace
    // comes from the store.
    workspace() {
      return this.$store.getters['workspace/get'](this.application.workspace.id)
    },
    identities() {
      return this.$store.getters['agent/getAllInWorkspace'](
        this.application.workspace.id
      )
    },
    selectedIdentity() {
      return this.$store.getters['agent/get'](
        this.application.agent_identity_id
      )
    },
    canCreateIdentity() {
      return (
        !this.readOnly &&
        this.workspace !== undefined &&
        this.$hasPermission('agent.create', this.workspace, this.workspace.id)
      )
    },
    agentIdentity: {
      get() {
        // The core application update isn't optimistic; the chosen identity
        // is shown from the moment it is picked until the save settles.
        return this.saving
          ? this.pendingIdentity
          : this.application.agent_identity_id || null
      },
      set(value) {
        this.saveIdentity(value)
      },
    },
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
    workspaceTool() {
      return this.$store.getters['agentApplication/getWorkspaceTool']
    },
    catalog() {
      return this.$store.getters['agentApplication/getWorkspaceToolCatalog']
    },
    config() {
      return normalizeWorkspaceConfig(this.workspaceTool?.config)
    },
    accessSegments() {
      return [
        { label: this.$t('agentAccess.accessEverything') },
        { label: this.$t('agentAccess.accessReadOnly') },
        { label: this.$t('agentAccess.accessCustom') },
      ]
    },
    accessIndex() {
      return ACCESS_ORDER.indexOf(this.config.access)
    },
    rules() {
      return effectiveRules(this.config, this.catalog)
    },
    groups() {
      const groups = new Map()
      for (const tool of this.catalog) {
        if (!groups.has(tool.group)) {
          groups.set(tool.group, {
            key: tool.group,
            label: tool.group_label,
            icon: GROUP_ICONS[tool.group] || 'iconoir-tools',
            tools: [],
          })
        }
        groups.get(tool.group).tools.push(tool)
      }
      return Array.from(groups.values()).map((group) => ({
        ...group,
        presetLabel: this.$t(
          `agentAccess.preset_${deriveGroupPreset(this.rules, group.tools)}`
        ),
      }))
    },
    extraBuiltIns() {
      return [
        {
          type: 'web_search',
          icon: 'iconoir-globe',
          label: this.$t('agentAccess.webSearch'),
          description: this.$t('agentAccess.webSearchDescription'),
        },
        {
          type: 'workspace_search',
          icon: 'iconoir-search',
          label: this.$t('agentAccess.workspaceSearch'),
          description: this.$t('agentAccess.workspaceSearchDescription'),
        },
      ]
    },
  },
  methods: {
    roleName(identity) {
      const roles = this.workspace?._?.roles || []
      return roles.find((role) => role.uid === identity.role_uid)?.name || ''
    },
    async onIdentityCreated(identity) {
      this.$store.dispatch('agent/forceCreate', identity)
      await this.saveIdentity(identity.id)
    },
    async saveIdentity(value) {
      if (this.readOnly || value === this.agentIdentity) {
        return
      }
      this.saving = true
      this.pendingIdentity = value
      try {
        await this.$store.dispatch('application/update', {
          application: this.application,
          values: { agent_identity_id: value },
        })
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.saving = false
      }
    },
    hasBuiltInTool(type) {
      return this.tools.some((tool) => tool.type === type)
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
          values: { config: { ...this.config, ...values } },
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
    onAccessChange(index) {
      const access = ACCESS_ORDER[index]
      if (!this.canUpdateTool) {
        return
      }
      if (access === this.config.access) {
        // Re-clicking "Custom" is the natural way back into the modal.
        if (access === ACCESS_CUSTOM) {
          this.$refs.permissionsModal.show()
        }
        return
      }
      if (access === ACCESS_CUSTOM) {
        // Custom starts from the current effective rules and is fine-tuned
        // in the modal.
        this.saveWorkspaceConfig({ access, tool_rules: { ...this.rules } })
        this.$refs.permissionsModal.show()
      } else {
        // Rules only apply to custom; stale ones would confuse the summary
        // and anyone reading the config.
        this.saveWorkspaceConfig({ access, tool_rules: {} })
      }
    },
    onAskChange(enabled) {
      const values = { require_write_approval: enabled }
      if (this.config.access === ACCESS_CUSTOM) {
        // Custom rules are explicit per tool and win over the flag, so the
        // enabled write tools follow the switch.
        const rule = enabled ? RULE_ASK : RULE_ALLOW
        const writeTools = new Set(
          this.catalog.filter((tool) => tool.is_write).map((tool) => tool.name)
        )
        values.tool_rules = Object.fromEntries(
          Object.entries(this.rules).map(([name, current]) => [
            name,
            writeTools.has(name) && current !== RULE_OFF ? rule : current,
          ])
        )
      }
      this.saveWorkspaceConfig(values)
    },
    openPermissions(group = undefined) {
      this.$refs.permissionsModal.show(group)
    },
  },
}
</script>
