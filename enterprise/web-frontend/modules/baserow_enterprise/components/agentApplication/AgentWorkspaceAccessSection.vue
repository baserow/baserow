<template>
  <FormGroup
    small-label
    :label="$t('agentWorkspaceAccess.identityLabel')"
    :helper-text="$t('agentWorkspaceAccess.identityHelper')"
  >
    <Dropdown
      v-model="agentIdentity"
      :disabled="readOnly || loadingAgents || saving"
      :show-footer="canCreateAgent"
    >
      <DropdownItem
        :name="$t('agentWorkspaceAccess.noneOption')"
        :value="null"
        icon="iconoir-prohibition"
      />
      <DropdownItem
        v-for="agent in agents"
        :key="agent.id"
        :name="agent.name"
        :value="agent.id"
        icon="baserow-icon-agent"
      />
      <template v-if="canCreateAgent" #footer>
        <a class="select__footer-button" @click="$refs.manageAgentModal.show()">
          <i class="iconoir-plus"></i>
          {{ $t('agentWorkspaceAccess.createAgent') }}
        </a>
      </template>
    </Dropdown>
    <ManageAgentModal
      v-if="canCreateAgent"
      ref="manageAgentModal"
      :workspace="workspace"
      :agent="null"
      @saved="onAgentCreated"
    />
  </FormGroup>
</template>

<script>
import AgentService from '@baserow/modules/core/services/agent'
import ManageAgentModal from '@baserow/modules/core/components/settings/agents/ManageAgentModal'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'AgentWorkspaceAccessSection',
  components: { ManageAgentModal },
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
      agents: [],
      loadingAgents: false,
      saving: false,
    }
  },
  computed: {
    // The application's workspace object doesn't carry the roles needed by
    // the manage agent modal, so the full workspace comes from the store.
    workspace() {
      return this.$store.getters['workspace/get'](this.application.workspace.id)
    },
    canCreateAgent() {
      return (
        !this.readOnly &&
        this.workspace !== undefined &&
        this.$hasPermission('agent.create', this.workspace, this.workspace.id)
      )
    },
    agentIdentity: {
      get() {
        return this.application.agent_identity_id || null
      },
      set(value) {
        this.save(value)
      },
    },
  },
  async mounted() {
    this.loadingAgents = true
    try {
      await this.fetchAgents()
    } finally {
      this.loadingAgents = false
    }
  },
  methods: {
    async fetchAgents() {
      try {
        const { data } = await AgentService(this.$client).list(
          this.application.workspace.id
        )
        this.agents = data.results
      } catch (error) {
        notifyIf(error, 'agent')
      }
    },
    async onAgentCreated(agent) {
      await this.fetchAgents()
      this.save(agent.id)
    },
    async save(value) {
      if (this.readOnly) {
        return
      }
      this.saving = true
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
  },
}
</script>
