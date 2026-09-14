<template>
  <Modal ref="modal">
    <h2 class="box__title">{{ $t('agentToolPermissions.title') }}</h2>
    <p class="agent-tool-permissions__description">
      {{ $t('agentToolPermissions.description', { name: agentName }) }}
    </p>
    <Tabs :key="tabsKey" v-model:selected-index="selectedIndex">
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
        <div class="agent-tool-permissions__table">
          <template v-for="section in sectionsFor(group)" :key="section.key">
            <div class="agent-tool-permissions__group-title">
              <span>{{ section.label }}</span>
              <span class="agent-tool-permissions__cell-header">{{
                $t('agentToolPermissions.allow')
              }}</span>
              <span class="agent-tool-permissions__cell-header">{{
                $t('agentToolPermissions.askFirst')
              }}</span>
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
            </div>
          </template>
        </div>
      </Tab>
    </Tabs>
    <div class="actions actions--right actions--gap">
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

const GROUP_ICONS = {
  database: 'iconoir-db',
  automation: 'baserow-icon-automation',
  builder: 'iconoir-app-window',
  core: 'iconoir-settings',
  search_user_docs: 'iconoir-search',
}

export default {
  name: 'AgentToolPermissionsModal',
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
      required: true,
    },
  },
  data() {
    return {
      rules: {},
      selectedIndex: 0,
      tabsKey: 0,
      saving: false,
    }
  },
  computed: {
    agentName() {
      return (
        this.$store.getters['agentApplication/getAgent']?.name ||
        this.application.name
      )
    },
    catalog() {
      return this.$store.getters['agentApplication/getWorkspaceToolCatalog']
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
    async save() {
      this.saving = true
      try {
        await this.$store.dispatch('agentApplication/updateTool', {
          toolId: this.tool.id,
          values: {
            config: buildPermissionsPayload(
              this.tool.config,
              this.rules,
              this.catalog
            ),
          },
        })
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
