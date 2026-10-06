<template>
  <Modal ref="modal">
    <h2 class="box__title">{{ $t('agentToolPermissions.title') }}</h2>
    <p class="agent-tool-permissions__description">
      {{ $t('agentToolPermissions.description', { name: agentName }) }}
    </p>
    <Tabs
      :key="tabsKey"
      v-model:selected-index="selectedIndex"
      :header-no-padding="true"
      :content-no-padding="true"
    >
      <Tab
        v-for="group in groups"
        :key="group.key"
        :title="group.label"
        :icon="group.icon"
      >
        <div class="agent-tool-permissions__preset">
          <Dropdown
            :model-value="presetFor(group)"
            :show-search="false"
            :fixed-items="true"
            :disabled="!canUpdate"
            @update:model-value="applyPreset(group, $event)"
          >
            <DropdownItem
              v-for="preset in presets"
              :key="preset.value"
              :name="preset.name"
              :value="preset.value"
              :description="preset.description"
            />
            <DropdownItem
              v-if="presetFor(group) === 'custom'"
              :name="$t('agentToolPermissions.presetCustom')"
              value="custom"
              :description="$t('agentToolPermissions.presetCustomDescription')"
            />
          </Dropdown>
          <div class="agent-tool-permissions__summary">
            {{ summaryFor(group) }}
          </div>
        </div>
        <div
          class="agent-tool-permissions__table"
          :class="{
            'agent-tool-permissions__table--identities': canPickIdentity,
          }"
        >
          <template v-for="section in sectionsFor(group)" :key="section.key">
            <div class="agent-tool-permissions__group-title">
              <span>{{ section.label }}</span>
              <span class="agent-tool-permissions__cell-header">{{
                $t('agentToolPermissions.allow')
              }}</span>
              <span class="agent-tool-permissions__cell-header">{{
                $t('agentToolPermissions.askFirst')
              }}</span>
              <span v-if="canPickIdentity"></span>
            </div>
            <div
              v-for="catalogTool in section.tools"
              :key="catalogTool.name"
              class="agent-tool-permissions__row"
            >
              <div class="agent-tool-permissions__row-label">
                <div class="agent-tool-permissions__row-title">
                  {{ catalogTool.label }}
                </div>
                <div class="agent-tool-permissions__row-description">
                  {{ catalogTool.description }}
                </div>
              </div>
              <div class="agent-tool-permissions__cell">
                <Checkbox
                  :checked="rules[catalogTool.name] !== 'off'"
                  :disabled="!canUpdate"
                  @input="setAllowed(catalogTool, $event)"
                ></Checkbox>
              </div>
              <div class="agent-tool-permissions__cell">
                <Checkbox
                  v-if="catalogTool.is_write"
                  :checked="rules[catalogTool.name] === 'ask'"
                  :disabled="!canUpdate || rules[catalogTool.name] === 'off'"
                  @input="setAsk(catalogTool, $event)"
                ></Checkbox>
              </div>
              <div v-if="canPickIdentity" class="agent-tool-permissions__cell">
                <ButtonIcon
                  icon="iconoir-more-vert"
                  size="small"
                  type="secondary"
                  class="agent-tool-permissions__more"
                  :title="$t('agentToolPermissions.runAs')"
                  @click="openIdentityMenu(catalogTool, $event.currentTarget)"
                ></ButtonIcon>
              </div>
            </div>
          </template>
        </div>
      </Tab>
    </Tabs>
    <div
      v-if="exceptions.length > 0"
      class="agent-tool-permissions__exceptions"
    >
      <div class="agent-tool-permissions__exceptions-head">
        <span>{{ $t('agentToolPermissions.exceptions') }}</span>
        <span class="agent-tool-permissions__exceptions-count">
          {{
            $t('agentToolPermissions.exceptionsCount', {
              count: exceptions.length,
            })
          }}
        </span>
      </div>
      <div class="agent-tool-permissions__exceptions-list">
        <div
          v-for="exception in exceptions"
          :key="exception.key"
          class="agent-tool-permissions__exception"
        >
          <Avatar
            :initials="exception.identity.name.slice(0, 1).toUpperCase()"
            color="green"
            size="small"
            rounded
          />
          <div class="agent-tool-permissions__exception-text">
            <div class="agent-tool-permissions__exception-title">
              {{ exception.label }}
            </div>
            <div class="agent-tool-permissions__exception-summary">
              {{
                $t('agentToolPermissions.runsAsSummary', {
                  name: exception.identity.name,
                  role: roleName(exception.identity),
                })
              }}
            </div>
          </div>
          <ButtonIcon
            v-if="canUpdate"
            icon="iconoir-bin"
            size="small"
            type="secondary"
            :loading="removingKeys.includes(exception.key)"
            :title="$t('agentToolPermissions.removeException')"
            @click="removeException(exception)"
          ></ButtonIcon>
        </div>
      </div>
      <div class="agent-tool-permissions__exceptions-note">
        {{ $t('agentToolPermissions.exceptionsNote') }}
      </div>
    </div>
    <Context
      ref="identityContext"
      class="agent-tool-permissions__identity-context"
      max-height-if-outside-viewport
    >
      <div v-if="identityTool" class="context__menu-title">
        {{ $t('agentToolPermissions.runToolAs', { name: identityTool.label }) }}
      </div>
      <ul class="context__menu">
        <li
          v-for="option in identityOptions"
          :key="option.key"
          class="context__menu-item"
        >
          <a
            class="context__menu-item-link context__menu-item-link--with-desc"
            :class="{ active: option.selected }"
            @click.prevent="pickIdentity(option.value)"
          >
            <span class="agent-tool-permissions__identity-option">
              <Avatar
                v-if="option.identity"
                :initials="option.identity.name.slice(0, 1).toUpperCase()"
                :color="option.value === null ? 'purple' : 'green'"
                size="small"
                rounded
              />
              <i v-else class="iconoir-prohibition"></i>
              <span class="context__menu-item-title-text">{{
                option.name
              }}</span>
              <span
                class="agent-tool-permissions__identity-description"
                :class="{
                  'agent-tool-permissions__identity-description--warning':
                    option.warning,
                }"
                >{{ option.description }}</span
              >
            </span>
            <i
              v-if="option.selected"
              class="context__menu-active-icon iconoir-check"
            ></i>
          </a>
        </li>
      </ul>
    </Context>
    <div class="actions actions--right actions--gap margin-bottom-0">
      <Button type="secondary" @click="hide()">
        {{ $t('agentToolPermissions.cancel') }}
      </Button>
      <Button
        type="primary"
        :loading="saving"
        :disabled="!canUpdate"
        @click="save"
      >
        {{ $t('agentToolPermissions.done') }}
      </Button>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import { notifyIf } from '@baserow/modules/core/utils/error'
import {
  effectiveRules,
  deriveGroupPreset,
  applyGroupPreset,
  buildPermissionsPayload,
  RULE_ALLOW,
  RULE_ASK,
  RULE_OFF,
} from '@baserow_enterprise/utils/agentToolPermissions'
import {
  workspaceToolIdentities,
  listToolIdentityExceptions,
  hasMoreAccess,
} from '@baserow_enterprise/utils/agentToolIdentities'
import { AgentContextMixin } from '@baserow_enterprise/composables/useAgentContext'

const GROUP_ICONS = {
  database: 'iconoir-db',
  automation: 'baserow-icon-automation',
  core: 'iconoir-settings',
}

export default {
  name: 'AgentToolPermissionsModal',
  mixins: [AgentContextMixin, modal],
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
      required: true,
    },
  },
  data() {
    return {
      rules: {},
      // Catalog tool name -> workspace agent id, saved with the rules.
      identities: {},
      identityTool: null,
      removingKeys: [],
      selectedIndex: 0,
      tabsKey: 0,
      saving: false,
    }
  },
  computed: {
    agentName() {
      return (
        this.$store.getters[`${this.storePrefix}agentApplication/getAgent`]
          ?.name || this.application.name
      )
    },
    catalog() {
      return this.$store.getters[
        `${this.storePrefix}agentApplication/getWorkspaceToolCatalog`
      ]
    },
    workspace() {
      return this.$store.getters['workspace/get'](this.application.workspace.id)
    },
    workspaceIdentities() {
      return this.$store.getters['agent/getAllInWorkspace'](
        this.application.workspace.id
      )
    },
    agentIdentity() {
      return this.$store.getters['agent/get'](
        this.application.agent_identity_id
      )
    },
    canPickIdentity() {
      return this.canUpdate
    },
    actionTools() {
      return this.$store.getters[
        `${this.storePrefix}agentApplication/getTools`
      ].filter((tool) => ['service', 'mcp'].includes(tool.type))
    },
    exceptions() {
      return listToolIdentityExceptions({
        workspaceTool: this.tool,
        actionTools: this.actionTools,
        catalog: this.catalog,
        identities: this.workspaceIdentities,
        overrides: this.identities,
      })
    },
    identityOptions() {
      if (!this.identityTool) {
        return []
      }
      const selected = this.identities[this.identityTool.name] ?? null
      const own = this.agentIdentity
      const options = [
        {
          key: 'own',
          value: null,
          identity: own,
          name: own ? own.name : this.$t('agentToolPermissions.noIdentity'),
          description: own
            ? this.$t('agentToolPermissions.agentsIdentity')
            : this.$t('agentToolPermissions.noIdentityDescription'),
          selected: selected === null,
          warning: false,
        },
      ]
      for (const identity of this.workspaceIdentities) {
        if (identity.id === own?.id) {
          continue
        }
        const moreAccess = hasMoreAccess(identity, own)
        options.push({
          key: identity.id,
          value: identity.id,
          identity,
          name: identity.name,
          description: moreAccess
            ? this.$t('agentToolPermissions.moreAccess')
            : this.roleName(identity),
          selected: selected === identity.id,
          warning: moreAccess,
        })
      }
      return options
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
      return Array.from(groups.values())
    },
    presets() {
      return ['everything', 'ask_first', 'read_only', 'off'].map((value) => ({
        value,
        name: this.$t(`agentToolPermissions.preset_${value}`),
        description: this.$t(`agentToolPermissions.preset_${value}Description`),
      }))
    },
  },
  methods: {
    show(group, ...args) {
      // Start from the effective rules so unlisted tools keep their
      // defaults when the config becomes custom.
      this.rules = effectiveRules(this.tool.config, this.catalog)
      this.identities = workspaceToolIdentities(this.tool.config)
      const index = this.groups.findIndex((item) => item.key === group)
      this.selectedIndex = index === -1 ? 0 : index
      this.tabsKey += 1
      modal.methods.show.call(this, ...args)
    },
    presetFor(group) {
      return deriveGroupPreset(this.rules, group.tools)
    },
    summaryFor(group) {
      const key = {
        everything: 'summaryEverything',
        ask_first: 'summaryAskFirst',
        read_only: 'summaryReadOnly',
        off: 'summaryOff',
        custom: 'summaryCustom',
      }[this.presetFor(group)]
      return this.$t(`agentToolPermissions.${key}`, {
        name: this.agentName,
        group: group.label.toLowerCase(),
      })
    },
    sectionsFor(group) {
      return [
        {
          key: 'reads',
          label: this.$t('agentToolPermissions.reads'),
          tools: group.tools.filter((tool) => !tool.is_write),
        },
        {
          key: 'changes',
          label: this.$t('agentToolPermissions.changes'),
          tools: group.tools.filter((tool) => tool.is_write),
        },
      ].filter((section) => section.tools.length > 0)
    },
    applyPreset(group, preset) {
      if (preset === 'custom') {
        return
      }
      this.rules = applyGroupPreset(this.rules, group.tools, preset)
    },
    setAllowed(tool, allowed) {
      if (!allowed) {
        this.rules = { ...this.rules, [tool.name]: RULE_OFF }
      } else {
        // Re-enabled writes ask first when the agent asks before changes.
        const ask =
          tool.is_write && this.tool.config?.require_write_approval !== false
        this.rules = { ...this.rules, [tool.name]: ask ? RULE_ASK : RULE_ALLOW }
      }
    },
    setAsk(tool, ask) {
      this.rules = { ...this.rules, [tool.name]: ask ? RULE_ASK : RULE_ALLOW }
    },
    roleName(identity) {
      const roles = this.workspace?._?.roles || []
      return roles.find((role) => role.uid === identity.role_uid)?.name || ''
    },
    openIdentityMenu(catalogTool, target) {
      this.identityTool = catalogTool
      this.$refs.identityContext.toggle(target, 'bottom', 'right', 4)
    },
    pickIdentity(identityId) {
      const name = this.identityTool.name
      const identities = { ...this.identities }
      if (identityId === null) {
        delete identities[name]
      } else {
        identities[name] = identityId
      }
      this.identities = identities
      this.$refs.identityContext.hide()
    },
    async removeException(exception) {
      if (exception.kind === 'workspace') {
        const identities = { ...this.identities }
        delete identities[exception.toolName]
        this.identities = identities
        return
      }
      // Action tool identities live on the tool itself, so the removal saves
      // right away instead of waiting for Done.
      this.removingKeys = [...this.removingKeys, exception.key]
      try {
        await this.$store.dispatch(
          `${this.storePrefix}agentApplication/updateTool`,
          {
            toolId: exception.tool.id,
            values: { identity_id: null },
          }
        )
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.removingKeys = this.removingKeys.filter(
          (key) => key !== exception.key
        )
      }
    },
    async save() {
      this.saving = true
      try {
        await this.$store.dispatch(
          `${this.storePrefix}agentApplication/updateTool`,
          {
            toolId: this.tool.id,
            values: {
              config: {
                ...buildPermissionsPayload(
                  this.tool.config,
                  this.rules,
                  this.catalog
                ),
                tool_identities: this.identities,
              },
            },
          }
        )
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
